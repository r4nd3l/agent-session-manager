"""Main window: composes the session sidebar with the tabbed terminal area."""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from . import __version__, dialogs
from .i18n import _
from .models import SessionItem
from .prefs import PreferencesDialog
from .providers import available_providers, get_provider
from .sessions import Session, export_markdown
from .sidebar import SessionSidebar
from .state import AppState
from .store import SessionStore
from .switcher import QuickSwitcher
from .terminal import TerminalTab

_GHOSTTY = shutil.which("ghostty")
_IDLE_NOTIFY_MS = 4000


def _make_tab_label(title: str, on_close) -> Gtk.Box:
    """Build a notebook tab label with a close button."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    label = Gtk.Label(label=title)
    label.set_ellipsize(3)  # Pango.EllipsizeMode.END
    label.set_max_width_chars(20)
    box.pack_start(label, True, True, 0)
    close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
    close_btn.get_style_context().add_class("flat")
    close_btn.set_relief(Gtk.ReliefStyle.NONE)
    close_btn.connect("clicked", on_close)
    box.pack_start(close_btn, False, False, 0)
    box.show_all()
    return box


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, state: AppState, store: SessionStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Agent Session Manager")
        self.set_icon_name("io.github.r4nd3l.AgentSessionManager")
        self.set_default_size(1280, 800)

        self.state = state
        self.store = store
        self._tabs: dict[str, TerminalTab] = {}  # session_id -> open tab
        self._confirmed_closes: set[TerminalTab] = set()
        self._closing_tabs: dict[TerminalTab, int] = {}
        self._tab_titles: dict[TerminalTab, str] = {}
        self._base_titles: dict[TerminalTab, str] = {}
        self._needs_attention: set[TerminalTab] = set()
        self._idle_sources: dict[TerminalTab, int] = {}
        self._switcher: QuickSwitcher | None = None

        self._install_actions()

        # --- content pane: header + notebook ---
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.set_show_tabs(True)
        self.notebook.connect("switch-page", self._on_page_switched)

        content_header = Gtk.HeaderBar()
        content_header.set_show_close_button(True)
        content_header.set_title("")
        content_header.set_has_subtitle(False)

        self.sidebar_toggle = Gtk.ToggleButton()
        self.sidebar_toggle.set_image(Gtk.Image.new_from_icon_name("view-sidebar-symbolic", Gtk.IconSize.BUTTON))
        self.sidebar_toggle.get_style_context().add_class("flat")
        self.sidebar_toggle.set_active(True)
        self.sidebar_toggle.set_tooltip_text(_("Toggle sidebar (F9)"))
        content_header.pack_start(self.sidebar_toggle)

        new_btn = Gtk.Button.new_from_icon_name("tab-new-symbolic", Gtk.IconSize.BUTTON)
        new_btn.set_tooltip_text(_("New session (Ctrl+Shift+T)"))
        new_btn.get_style_context().add_class("flat")
        new_btn.get_style_context().add_class("cc-accent-btn")
        new_btn.connect("clicked", lambda *_: self._new_session())
        content_header.pack_start(new_btn)

        self.close_all_btn = Gtk.Button.new_from_icon_name("edit-clear-all-symbolic", Gtk.IconSize.BUTTON)
        self.close_all_btn.get_style_context().add_class("flat")
        self.close_all_btn.set_tooltip_text(_("Close all tabs"))
        self.close_all_btn.set_no_show_all(True)
        self.close_all_btn.set_visible(False)
        self.close_all_btn.connect("clicked", lambda *_: self._close_all_tabs())
        content_header.pack_start(self.close_all_btn)

        self.set_titlebar(content_header)

        # Placeholder when no tabs
        self._placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._placeholder.set_valign(Gtk.Align.CENTER)
        self._placeholder.set_halign(Gtk.Align.CENTER)

        logo_text = (
            "     _    ____  __  __\n"
            "    / \\  / ___||  \\/  |\n"
            "   / _ \\ \\___ \\| |\\/| |\n"
            "  / ___ \\ ___) | |  | |\n"
            " /_/   \\_\\____/|_|  |_|\n"
        )
        logo = Gtk.Label(label=logo_text)
        logo.get_style_context().add_class("cc-logo-art")
        self._placeholder.pack_start(logo, False, False, 0)

        ph_title = Gtk.Label(label=_("No session open"))
        ph_title.get_style_context().add_class("cc-placeholder-title")
        ph_title.set_margin_top(8)
        self._placeholder.pack_start(ph_title, False, False, 0)

        ph_desc = Gtk.Label(label=_("Pick a session from the sidebar, or start a new one."))
        ph_desc.get_style_context().add_class("cc-placeholder-desc")
        self._placeholder.pack_start(ph_desc, False, False, 0)

        shortcuts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        shortcuts_box.set_margin_top(24)
        for keys, desc in [
            (["Ctrl", "Shift", "T"], _("New session")),
            (["Ctrl", "Shift", "K"], _("Quick switch")),
            (["Ctrl", ","], _("Preferences")),
            (["F9"], _("Toggle sidebar")),
        ]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.set_halign(Gtk.Align.CENTER)
            key_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            key_box.set_size_request(180, -1)
            key_box.set_halign(Gtk.Align.END)
            for k in keys:
                kbd = Gtk.Label(label=k)
                kbd.get_style_context().add_class("cc-kbd")
                key_box.pack_start(kbd, False, False, 0)
            row.pack_start(key_box, False, False, 0)
            desc_label = Gtk.Label(label=desc, xalign=0.0)
            desc_label.get_style_context().add_class("cc-placeholder-desc")
            desc_label.set_size_request(140, -1)
            row.pack_start(desc_label, False, False, 0)
            shortcuts_box.pack_start(row, False, False, 0)
        self._placeholder.pack_start(shortcuts_box, False, False, 0)

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(self._placeholder, "empty")
        self.content_stack.add_named(self.notebook, "tabs")

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.pack_start(self.content_stack, True, True, 0)

        # --- sidebar ---
        self.sidebar = SessionSidebar(self.store)
        self.sidebar.connect("open-session", self._on_sidebar_open)
        self.sidebar.connect("open-many", self._on_sidebar_open_many)
        self.sidebar.connect("trash-many", self._on_sidebar_trash_many)

        self.sidebar.set_size_request(220, -1)
        self.split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.split.pack1(self.sidebar, resize=False, shrink=False)
        self.split.pack2(content_box, resize=True, shrink=False)
        self.split.set_position(int(self.state.get_setting("sidebar_width")))
        self.split.connect("notify::position", self._schedule_save_sidebar_width)
        self.add(self.split)

        self._sidebar_width_save_source: int | None = None
        self.sidebar_toggle.connect(
            "toggled", lambda b: self.sidebar.set_visible(b.get_active())
        )

        # Keyboard shortcuts
        self.connect("key-press-event", self._on_key_press)

    # -- sidebar width persistence -------------------------------------------

    def _schedule_save_sidebar_width(self, *_args) -> None:
        if not self.sidebar.get_visible():
            return
        if self._sidebar_width_save_source is not None:
            GLib.source_remove(self._sidebar_width_save_source)
        self._sidebar_width_save_source = GLib.timeout_add(600, self._save_sidebar_width)

    def _save_sidebar_width(self) -> bool:
        self._sidebar_width_save_source = None
        position = self.split.get_position()
        if position >= 150:
            self.state.set_setting("sidebar_width", position)
        return GLib.SOURCE_REMOVE

    # -- keyboard shortcuts ---------------------------------------------------

    def _on_key_press(self, _widget, event: Gdk.EventKey) -> bool:
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        keyval = event.keyval
        ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK

        if state == ctrl_shift:
            if keyval == Gdk.KEY_F:
                self.sidebar.focus_search()
                return True
            if keyval == Gdk.KEY_T:
                self._new_session()
                return True
            if keyval == Gdk.KEY_W:
                self._close_current_tab()
                return True
            if keyval == Gdk.KEY_K:
                self._quick_switch()
                return True
        if state == Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_Page_Down:
                self._next_tab()
                return True
            if keyval == Gdk.KEY_Page_Up:
                self._prev_tab()
                return True
            if keyval == Gdk.KEY_comma:
                self._show_preferences()
                return True
        if keyval == Gdk.KEY_F9 and state == 0:
            self.sidebar.set_visible(not self.sidebar.get_visible())
            self.sidebar_toggle.set_active(self.sidebar.get_visible())
            return True
        return False

    # -- actions / shortcuts -------------------------------------------------

    def _install_actions(self) -> None:
        plain = {
            "refresh": lambda *_: self.store.refresh(),
            "new-session": lambda *_: self._new_session(),
            "preferences": lambda *_: self._show_preferences(),
            "mcp-servers": lambda *_: dialogs.mcp_browser_dialog(self),
            "focus-search": lambda *_: self.sidebar.focus_search(),
            "close-tab": lambda *_: self._close_current_tab(),
            "next-tab": lambda *_: self._next_tab(),
            "prev-tab": lambda *_: self._prev_tab(),
            "about": lambda *_: self._show_about(),
            "quick-switch": lambda *_: self._quick_switch(),
            "toggle-sidebar": lambda *_: self.sidebar.set_visible(
                not self.sidebar.get_visible()
            ),
        }
        for name, callback in plain.items():
            action = Gio.SimpleAction(name=name)
            action.connect("activate", callback)
            self.add_action(action)

        per_session = {
            "new-session-provider": lambda _a, p: self._choose_new_session_folder(
                get_provider(p.get_string())
            ),
            "open-session": self._on_open_action,
            "fork-session": self._on_fork_action,
            "open-ghostty": self._on_open_ghostty,
            "rename-session": self._on_rename_action,
            "toggle-favorite": lambda _a, p: self.store.toggle_favorite(p.get_string()),
            "copy-session-id": lambda _a, p: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(p.get_string(), -1),
            "reveal-transcript": self._on_reveal_transcript,
            "export-session": self._on_export_session,
            "session-details": self._on_session_details,
            "hide-session": self._on_hide_session,
            "trash-session": self._on_trash_session,
        }
        for name, callback in per_session.items():
            action = Gio.SimpleAction(name=name, parameter_type=GLib.VariantType("s"))
            action.connect("activate", callback)
            self.add_action(action)

        show_hidden = Gio.SimpleAction.new_stateful(
            "show-hidden", None, GLib.Variant.new_boolean(False)
        )
        show_hidden.connect("change-state", self._on_show_hidden)
        self.add_action(show_hidden)

    # -- sidebar signal handlers -------------------------------------------------

    def _on_sidebar_open(self, _sidebar, item: SessionItem, fork: bool) -> None:
        self.open_session(item.session, fork=fork)

    def _on_sidebar_open_many(self, _sidebar, items: list[SessionItem]) -> None:
        for item in items:
            self.open_session(item.session)

    def _on_sidebar_trash_many(self, _sidebar, items: list[SessionItem]) -> None:
        def do_trash() -> None:
            errors = []
            for item in items:
                error = self.store.trash(item.session_id)
                if error:
                    errors.append(f"{item.display_name}: {error}")
                    continue
                tab = self._tabs.get(item.session_id)
                if tab is not None:
                    self._remove_tab(tab)
            if errors:
                dialogs.error_dialog(self, _("Some transcripts could not be trashed"), "\n".join(errors))

        dialogs.confirm_dialog(
            self,
            _("Move {n} transcript(s) to trash?").format(n=len(items)),
            _("The files are moved to the trash and can be restored."),
            _("Move to Trash"),
            do_trash,
        )

    # -- tabs --------------------------------------------------------------

    def open_session(self, session: Session, fork: bool = False) -> None:
        provider = get_provider(session.provider)
        fork = fork and provider.supports_fork
        if not fork:
            tab = self._tabs.get(session.session_id)
            if tab is not None:
                page_num = self.notebook.page_num(tab)
                if page_num >= 0:
                    self.notebook.set_current_page(page_num)
                    return

        tab = TerminalTab(
            cwd=session.cwd,
            session_id=session.session_id,
            fork=fork,
            settings=self.state.settings,
            provider=provider,
        )
        title = f"{self.store.display_name(session)} (fork)" if fork else self._tab_title(session)
        self._add_tab(tab, title,
                      f"{session.project_name} — {session.session_id}")
        if not fork:
            self._tabs[session.session_id] = tab
            self._sync_status(session.session_id)

    def _tab_title(self, session: Session) -> str:
        name = self.store.display_name(session)
        emoji = self.state.get_emoji(session.session_id)
        return f"{emoji} {name}" if emoji else name

    def _default_provider(self):
        providers = available_providers()
        return providers[0] if providers else get_provider("claude")

    def _new_session(self, provider=None) -> None:
        provider = provider or self._default_provider()
        default = self.state.get_setting("new_session_dir")
        if default and Path(default).is_dir():
            self._start_new_session(default, provider)
        else:
            self._choose_new_session_folder(provider)

    def _choose_new_session_folder(self, provider=None) -> None:
        self._new_session_provider = provider or self._default_provider()
        dialog = Gtk.FileChooserDialog(
            title=_("Choose project directory"),
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Open"), Gtk.ResponseType.OK)
        default = self.state.get_setting("new_session_dir")
        if default and Path(default).is_dir():
            dialog.set_current_folder(default)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            cwd = dialog.get_filename()
            self.state.set_setting("new_session_dir", cwd)
            self._start_new_session(cwd, getattr(self, "_new_session_provider", None))
        dialog.destroy()

    def _start_new_session(self, cwd: str, provider=None) -> None:
        provider = provider or self._default_provider()
        tab = TerminalTab(
            cwd=cwd, session_id=None, settings=self.state.settings, provider=provider
        )
        self._add_tab(
            tab,
            GLib.path_get_basename(cwd),
            f"new {provider.name} session — {cwd}",
        )

    def _add_tab(self, tab: TerminalTab, title: str, tooltip: str) -> None:
        self._tab_titles[tab] = title
        self._base_titles[tab] = title

        def on_close_clicked(_btn, t=tab):
            self._request_close_tab(t)

        tab_label = _make_tab_label(title, on_close_clicked)
        tab_label.set_tooltip_text(tooltip)
        tab_label.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        tab_label.connect("button-press-event", self._on_tab_label_button_press, tab)

        page_num = self.notebook.append_page(tab, tab_label)
        self.notebook.set_tab_reorderable(tab, True)
        tab.connect("process-exited", self._on_process_exited)
        tab.terminal.connect("contents-changed", self._on_terminal_output, tab)
        self.notebook.set_current_page(page_num)
        self.content_stack.set_visible_child_name("tabs")
        self.close_all_btn.set_visible(self.notebook.get_n_pages() > 1)
        tab.show_all()
        GLib.idle_add(tab.grab_terminal_focus)

    def _update_tab_title(self, tab: TerminalTab, title: str) -> None:
        self._tab_titles[tab] = title
        page_num = self.notebook.page_num(tab)
        if page_num < 0:
            return

        def on_close_clicked(_btn, t=tab):
            self._request_close_tab(t)

        new_label = _make_tab_label(title, on_close_clicked)
        new_label.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        new_label.connect("button-press-event", self._on_tab_label_button_press, tab)
        tooltip = self.notebook.get_tab_label(tab)
        if tooltip:
            new_label.set_tooltip_text(tooltip.get_tooltip_text() or "")
        self.notebook.set_tab_label(tab, new_label)

    def _request_close_tab(self, tab: TerminalTab) -> None:
        if tab in self._confirmed_closes or not tab.has_running_command():
            self._remove_tab(tab)
            return
        if tab not in self._closing_tabs:
            self._graceful_close(tab)

    def _remove_tab(self, tab: TerminalTab) -> None:
        self._confirmed_closes.discard(tab)
        self._closing_tabs.pop(tab, None)
        self._tab_titles.pop(tab, None)
        self._base_titles.pop(tab, None)
        self._needs_attention.discard(tab)
        self._cancel_idle(tab)

        session_id = self._session_id_of(tab)
        if session_id:
            self._tabs.pop(session_id, None)
            self._sync_status(session_id)

        page_num = self.notebook.page_num(tab)
        if page_num >= 0:
            self.notebook.remove_page(page_num)

        if self.notebook.get_n_pages() == 0:
            self.content_stack.set_visible_child_name("empty")
        self.close_all_btn.set_visible(self.notebook.get_n_pages() > 1)

    def _close_current_tab(self) -> None:
        page_num = self.notebook.get_current_page()
        if page_num >= 0:
            tab = self.notebook.get_nth_page(page_num)
            if isinstance(tab, TerminalTab):
                self._request_close_tab(tab)

    def _close_all_tabs(self) -> None:
        tabs = []
        for i in range(self.notebook.get_n_pages()):
            tab = self.notebook.get_nth_page(i)
            if isinstance(tab, TerminalTab):
                tabs.append(tab)
        for tab in tabs:
            self._request_close_tab(tab)

    def _next_tab(self) -> None:
        if self.notebook.get_current_page() < self.notebook.get_n_pages() - 1:
            self.notebook.next_page()

    def _prev_tab(self) -> None:
        if self.notebook.get_current_page() > 0:
            self.notebook.prev_page()

    def _graceful_close(self, tab: TerminalTab) -> None:
        exit_text = tab.provider.graceful_exit()
        if not exit_text:
            self._confirmed_closes.add(tab)
            self._remove_tab(tab)
            return
        self._closing_tabs[tab] = 0
        tab.feed_child_text(exit_text)
        GLib.timeout_add(300, self._poll_graceful, tab)

    def _poll_graceful(self, tab: TerminalTab) -> bool:
        if tab not in self._closing_tabs:
            return GLib.SOURCE_REMOVE
        if not tab.has_running_command():
            tab.feed_child_text("exit\r")
            return GLib.SOURCE_REMOVE
        self._closing_tabs[tab] += 1
        if self._closing_tabs[tab] >= 40:
            self._confirmed_closes.add(tab)
            self._remove_tab(tab)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _sync_status(self, session_id: str) -> None:
        tab = self._tabs.get(session_id)
        if tab is None:
            status = ""
        elif tab in self._needs_attention:
            status = "attention"
        else:
            status = "open"
        self.store.set_status(session_id, status)
        self.sidebar.update_footer()

    def _session_id_of(self, tab: TerminalTab) -> str | None:
        if tab.session_id and not tab.fork:
            return tab.session_id
        return None

    def _on_terminal_output(self, _terminal, tab: TerminalTab) -> None:
        current_page = self.notebook.get_current_page()
        if current_page >= 0 and self.notebook.get_nth_page(current_page) is tab:
            return
        if tab not in self._needs_attention:
            self._needs_attention.add(tab)
            session_id = self._session_id_of(tab)
            if session_id:
                self._sync_status(session_id)
        if self.state.get_setting("notify_idle"):
            self._schedule_idle_notify(tab)

    def _on_page_switched(self, notebook: Gtk.Notebook, page: Gtk.Widget, page_num: int) -> None:
        if not isinstance(page, TerminalTab):
            return
        self._cancel_idle(page)
        if page in self._needs_attention:
            self._needs_attention.discard(page)
            session_id = self._session_id_of(page)
            if session_id:
                self._sync_status(session_id)
        GLib.idle_add(page.grab_terminal_focus)

    # -- idle notifications --------------------------------------------------

    def _schedule_idle_notify(self, tab: TerminalTab) -> None:
        self._cancel_idle(tab)
        self._idle_sources[tab] = GLib.timeout_add(_IDLE_NOTIFY_MS, self._fire_idle_notify, tab)

    def _cancel_idle(self, tab: TerminalTab) -> None:
        source = self._idle_sources.pop(tab, None)
        if source is not None:
            GLib.source_remove(source)

    def _fire_idle_notify(self, tab: TerminalTab) -> bool:
        self._idle_sources.pop(tab, None)
        current_page = self.notebook.get_current_page()
        if current_page >= 0 and self.notebook.get_nth_page(current_page) is tab:
            return GLib.SOURCE_REMOVE
        if not self.state.get_setting("notify_idle"):
            return GLib.SOURCE_REMOVE
        app = self.get_application()
        if app is not None:
            title = self._tab_titles.get(tab, "Session")
            session_id = self._session_id_of(tab) or ""
            notification = Gio.Notification.new(title)
            notification.set_body("Claude finished responding.")
            notification.set_default_action_and_target(
                "app.focus-session", GLib.Variant("s", session_id)
            )
            app.send_notification(session_id or title, notification)
        return GLib.SOURCE_REMOVE

    def focus_session(self, session_id: str) -> None:
        tab = self._tabs.get(session_id)
        if tab is not None:
            page_num = self.notebook.page_num(tab)
            if page_num >= 0:
                self.notebook.set_current_page(page_num)

    # -- tab events ---------------------------------------------------

    def _on_tab_label_button_press(self, _label, event: Gdk.EventButton, tab: TerminalTab) -> bool:
        if event.button == 3:
            self._show_tab_menu(tab, event)
            return True
        return False

    def _show_tab_menu(self, tab: TerminalTab, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        def add_item(label: str, callback, sensitive: bool = True) -> None:
            item = Gtk.MenuItem(label=label)
            item.set_sensitive(sensitive)
            item.connect("activate", lambda *_: callback())
            menu.append(item)

        add_item(_("Rename…"), lambda: self._rename_tab(tab))
        add_item(_("Set emoji…"), lambda: self._set_tab_emoji(tab))
        add_item(
            _("Copy session ID"),
            lambda: self._copy_tab_session_id(tab),
            bool(tab.session_id),
        )
        menu.append(Gtk.SeparatorMenuItem())
        add_item(_("Close tab"), lambda: self._request_close_tab(tab))

        menu.attach_to_widget(self.notebook, None)
        menu.connect("deactivate", lambda m: m.destroy())
        menu.show_all()
        menu.popup_at_pointer(event)

    def _rename_tab(self, tab: TerminalTab) -> None:
        session_id = self._session_id_of(tab)
        if session_id:
            session = self.store.get_session(session_id)
            if session is not None:
                self._prompt_rename_session(session)
            return

        current = self._tab_titles.get(tab, "")

        def save(name: str) -> None:
            name = name.strip()
            if not name:
                return
            self._base_titles[tab] = name
            self._update_tab_title(tab, name)

        dialogs.rename_dialog(self, _("Tab name"), current, save)

    def _set_tab_emoji(self, tab: TerminalTab) -> None:
        session_id = self._session_id_of(tab)
        if session_id:
            current = self.state.get_emoji(session_id) or ""

            def save(emoji: str) -> None:
                self.state.set_emoji(session_id, emoji.strip())
                session = self.store.get_session(session_id)
                if session is not None:
                    self._update_tab_title(tab, self._tab_title(session))

            dialogs.emoji_dialog(self, current, save)
            return

        base = self._base_titles.get(tab, self._tab_titles.get(tab, "Session"))

        def save(emoji: str) -> None:
            emoji = emoji.strip()
            self._update_tab_title(tab, f"{emoji} {base}" if emoji else base)

        dialogs.emoji_dialog(self, "", save)

    def _copy_tab_session_id(self, tab: TerminalTab) -> None:
        if tab.session_id:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(tab.session_id, -1)

    def _on_process_exited(self, tab: TerminalTab, _status: int) -> None:
        self._remove_tab(tab)

    # -- per-session actions ---------------------------------------------------

    def _session_for(self, param: GLib.Variant) -> Session | None:
        return self.store.get_session(param.get_string())

    def _on_open_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session:
            self.open_session(session)

    def _on_fork_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session:
            self.open_session(session, fork=True)

    def _on_open_ghostty(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None or _GHOSTTY is None:
            return
        provider = get_provider(session.provider)
        if shutil.which(provider.cli) is None:
            return
        cwd = session.cwd if session.cwd and Path(session.cwd).is_dir() else str(Path.home())
        subprocess.Popen(
            [_GHOSTTY, f"--working-directory={cwd}", "-e",
             provider.cli, "--resume", session.session_id],
            start_new_session=True,
        )

    def _on_rename_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is not None:
            self._prompt_rename_session(session)

    def _prompt_rename_session(self, session: Session) -> None:
        def save(name: str) -> None:
            self.store.rename(session.session_id, name)
            tab = self._tabs.get(session.session_id)
            if tab is not None:
                self._update_tab_title(tab, self._tab_title(session))

        dialogs.rename_dialog(
            self,
            session.preview or session.session_id,
            self.state.get_name(session.session_id) or "",
            save,
        )

    def _on_reveal_transcript(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return
        parent_dir = str(session.jsonl_path.parent)
        try:
            subprocess.Popen(["xdg-open", parent_dir], start_new_session=True)
        except OSError:
            pass

    def _on_export_session(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return
        title = self.store.display_name(session)
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip() or "session"

        dialog = Gtk.FileChooserDialog(
            title=_("Export session as Markdown"),
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Save"), Gtk.ResponseType.OK)
        dialog.set_current_name(f"{safe}.md")
        dialog.set_do_overwrite_confirmation(True)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            dest = dialog.get_filename()

            def work() -> None:
                error = None
                try:
                    text = export_markdown(session.jsonl_path, title, session.session_id, session.cwd)
                    Path(dest).write_text(text, encoding="utf-8")
                except OSError as err:
                    error = str(err)
                if error:
                    GLib.idle_add(dialogs.error_dialog, self, _("Export failed"), error)

            threading.Thread(target=work, daemon=True).start()
        dialog.destroy()

    def _on_session_details(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is not None:
            dialogs.details_dialog(self, session, self.store.display_name(session))

    def _on_hide_session(self, _action, param: GLib.Variant) -> None:
        session_id = param.get_string()
        self.store.set_hidden(session_id, not self.state.is_hidden(session_id))

    def _on_show_hidden(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.store.set_show_hidden(value.get_boolean())

    def _on_trash_session(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return

        def do_trash() -> None:
            error = self.store.trash(session.session_id)
            if error:
                dialogs.error_dialog(self, _("Could not trash transcript"), error)
                return
            tab = self._tabs.get(session.session_id)
            if tab is not None:
                self._remove_tab(tab)

        dialogs.confirm_dialog(
            self,
            _("Move transcript to trash?"),
            _("“{name}” will be removed from Claude’s history.").format(
                name=self.store.display_name(session)
            )
            + "\n"
            + _("The file is moved to the trash and can be restored."),
            _("Move to Trash"),
            do_trash,
        )

    # -- preferences / about -------------------------------------------------

    def _show_about(self) -> None:
        about = Gtk.AboutDialog(
            transient_for=self,
            modal=True,
            program_name="Agent Session Manager",
            logo_icon_name="io.github.r4nd3l.AgentSessionManager",
            version=__version__,
            license_type=Gtk.License.GPL_3_0,
            comments=_(
                "Manage and resume your AI coding agent sessions.\n\n"
                "Unofficial community tool — not affiliated with or endorsed by Anthropic."
            ),
            website="https://github.com/r4nd3l/agent-session-manager",
        )
        about.run()
        about.destroy()

    def _quick_switch(self) -> None:
        if self._switcher is not None:
            return
        self._switcher = QuickSwitcher(self.store, lambda item: self.open_session(item.session), parent=self)
        self._switcher.connect("destroy", lambda *_: setattr(self, "_switcher", None))
        self._switcher.present_switcher(self)

    def _show_preferences(self) -> None:
        PreferencesDialog(self.state, self._apply_settings_to_tabs, parent=self).present_prefs(self)

    def _apply_settings_to_tabs(self) -> None:
        for i in range(self.notebook.get_n_pages()):
            tab = self.notebook.get_nth_page(i)
            if isinstance(tab, TerminalTab):
                tab.apply_settings(self.state.settings)
