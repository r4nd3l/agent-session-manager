"""Main window: composes the session sidebar with the tabbed terminal area."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

from . import __version__, dialogs
from .models import SessionItem
from .prefs import PreferencesDialog, apply_color_scheme
from .sessions import Session
from .sidebar import SessionSidebar
from .state import AppState
from .store import SessionStore
from .switcher import QuickSwitcher
from .terminal import TerminalTab

_GHOSTTY = shutil.which("ghostty")

# Quiet period before a background tab is considered "idle" / finished.
_IDLE_NOTIFY_MS = 4000

# Tab status dots, matching the sidebar (.status-dot CSS in app.py).
_STATUS_COLORS = {"open": "#2ec27e", "attention": "#3584e4"}
_status_icon_cache: dict[str, Gio.Icon] = {}


def _status_icon(status: str) -> Gio.Icon | None:
    if status not in _STATUS_COLORS:
        return None
    icon = _status_icon_cache.get(status)
    if icon is None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
            f'<circle cx="8" cy="8" r="4" fill="{_STATUS_COLORS[status]}"/></svg>'
        ).encode()
        icon = Gio.BytesIcon.new(GLib.Bytes.new(svg))
        _status_icon_cache[status] = icon
    return icon


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Claude Session Manager")
        self.set_icon_name("eu.zengo.ClaudeSessionManager")
        self.set_default_size(1280, 800)

        self.state = AppState()
        apply_color_scheme(self.state.get_setting("color_scheme"))

        self.store = SessionStore(self.state)
        self._pages: dict[str, Adw.TabPage] = {}  # session_id -> open tab
        self._confirmed_closes: set[Adw.TabPage] = set()
        self._closing_pages: dict[Adw.TabPage, int] = {}  # graceful close in progress -> attempts
        self._menu_page: Adw.TabPage | None = None
        self._base_titles: dict[Adw.TabPage, str] = {}  # fork/new tab title without emoji
        self._idle_sources: dict[Adw.TabPage, int] = {}  # pending idle-notify timers
        self._switcher: QuickSwitcher | None = None

        self._install_actions()
        self._install_shortcuts()

        # --- content pane: header + tab bar + tab view ---
        self.tab_view = Adw.TabView()
        self.tab_view.connect("close-page", self._on_close_page)
        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)
        self.tab_view.connect("setup-menu", self._on_tab_setup_menu)

        tab_menu = Gio.Menu()
        tab_menu.append("Rename…", "win.rename-tab")
        tab_menu.append("Set emoji…", "win.set-tab-emoji")
        tab_menu.append("Copy session ID", "win.copy-tab-session-id")
        tab_menu.append("Close", "win.close-menu-tab")
        self.tab_view.set_menu_model(tab_menu)

        tab_bar = Adw.TabBar(view=self.tab_view)
        tab_bar.set_autohide(False)

        content_header = Adw.HeaderBar()
        self.sidebar_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic", active=True)
        self.sidebar_toggle.set_tooltip_text("Toggle sidebar (F9)")
        content_header.pack_start(self.sidebar_toggle)

        new_btn = Gtk.Button(icon_name="tab-new-symbolic")
        new_btn.set_tooltip_text("New Claude session… (Ctrl+Shift+T)")
        new_btn.set_action_name("win.new-session")
        content_header.pack_start(new_btn)

        self.close_all_btn = Gtk.Button(icon_name="tab-close-symbolic", visible=False)
        self.close_all_btn.set_tooltip_text("Close all tabs")
        self.close_all_btn.connect("clicked", lambda *_: self._close_all_tabs())
        content_header.pack_start(self.close_all_btn)
        self.tab_view.connect(
            "notify::n-pages",
            lambda *_: self.close_all_btn.set_visible(self.tab_view.get_n_pages() > 1),
        )

        placeholder = Adw.StatusPage(
            icon_name="utilities-terminal-symbolic",
            title="No session open",
            description="Pick a session from the sidebar, or start a new one.",
        )

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(placeholder, "empty")
        self.content_stack.add_named(self.tab_view, "tabs")

        content_view = Adw.ToolbarView()
        content_view.add_top_bar(content_header)
        content_view.add_top_bar(tab_bar)
        content_view.set_content(self.content_stack)

        # --- sidebar ---
        self.sidebar = SessionSidebar(self.store)
        self.sidebar.connect("open-session", self._on_sidebar_open)
        self.sidebar.connect("open-many", self._on_sidebar_open_many)
        self.sidebar.connect("trash-many", self._on_sidebar_trash_many)

        self.split = Adw.OverlaySplitView()
        self.split.set_sidebar(self.sidebar)
        self.split.set_content(content_view)
        self.split.set_min_sidebar_width(280)
        self.split.set_max_sidebar_width(400)
        self.set_content(self.split)

        self.split.bind_property(
            "show-sidebar",
            self.sidebar_toggle,
            "active",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        self.store.start()

    # -- actions / shortcuts -------------------------------------------------

    def _install_actions(self) -> None:
        plain = {
            "refresh": lambda *_: self.store.refresh(),
            "new-session": lambda *_: self._new_session(),
            "preferences": lambda *_: self._show_preferences(),
            "focus-search": lambda *_: self.sidebar.focus_search(),
            "close-tab": lambda *_: self._close_current_tab(),
            "next-tab": lambda *_: self.tab_view.select_next_page(),
            "prev-tab": lambda *_: self.tab_view.select_previous_page(),
            "about": lambda *_: self._show_about(),
            "quick-switch": lambda *_: self._quick_switch(),
            "rename-tab": lambda *_: self._rename_tab(),
            "set-tab-emoji": lambda *_: self._set_tab_emoji(),
            "copy-tab-session-id": lambda *_: self._copy_tab_session_id(),
            "close-menu-tab": lambda *_: self._close_menu_tab(),
            "toggle-sidebar": lambda *_: self.split.set_show_sidebar(
                not self.split.get_show_sidebar()
            ),
        }
        for name, callback in plain.items():
            action = Gio.SimpleAction(name=name)
            action.connect("activate", callback)
            self.add_action(action)

        per_session = {
            "open-session": self._on_open_action,
            "fork-session": self._on_fork_action,
            "open-ghostty": self._on_open_ghostty,
            "rename-session": self._on_rename_action,
            "toggle-favorite": lambda _a, p: self.store.toggle_favorite(p.get_string()),
            "copy-session-id": lambda _a, p: self.get_clipboard().set(p.get_string()),
            "reveal-transcript": self._on_reveal_transcript,
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

    def _install_shortcuts(self) -> None:
        controller = Gtk.ShortcutController()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        for trigger, action in (
            ("<Control><Shift>f", "win.focus-search"),
            ("<Control><Shift>t", "win.new-session"),
            ("<Control><Shift>w", "win.close-tab"),
            ("<Control>Page_Down", "win.next-tab"),
            ("<Control>Page_Up", "win.prev-tab"),
            ("<Control>comma", "win.preferences"),
            ("<Control><Shift>k", "win.quick-switch"),
            ("F9", "win.toggle-sidebar"),
        ):
            controller.add_shortcut(
                Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(trigger), Gtk.NamedAction.new(action)
                )
            )
        self.add_controller(controller)

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
                page = self._pages.get(item.session_id)
                if page is not None:
                    self.tab_view.close_page(page)
            if errors:
                dialogs.error_dialog(self, "Some transcripts could not be trashed", "\n".join(errors))

        dialogs.confirm_dialog(
            self,
            f"Move {len(items)} transcript(s) to trash?",
            "The files are moved to the trash and can be restored.",
            "Move to Trash",
            do_trash,
        )

    # -- tabs --------------------------------------------------------------

    def open_session(self, session: Session, fork: bool = False) -> None:
        if not fork:
            page = self._pages.get(session.session_id)
            if page is not None:
                self.tab_view.set_selected_page(page)
                return

        tab = TerminalTab(
            cwd=session.cwd,
            session_id=session.session_id,
            fork=fork,
            settings=self.state.settings,
        )
        title = f"{self.store.display_name(session)} (fork)" if fork else self._tab_title(session)
        page = self._add_tab(tab, title,
                             f"{session.project_name} — {session.session_id}")
        if not fork:
            self._pages[session.session_id] = page
            self._sync_status(session.session_id)

    def _tab_title(self, session: Session) -> str:
        """Tab title with the session's saved emoji prefix (tabs only)."""
        name = self.store.display_name(session)
        emoji = self.state.get_emoji(session.session_id)
        return f"{emoji} {name}" if emoji else name

    def _new_session(self) -> None:
        dialog = Gtk.FileDialog(title="Choose project directory")
        dialog.select_folder(self, None, self._on_new_session_folder)

    def _on_new_session_folder(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return  # cancelled
        cwd = folder.get_path()
        tab = TerminalTab(cwd=cwd, session_id=None, settings=self.state.settings)
        self._add_tab(tab, GLib.path_get_basename(cwd), f"new session — {cwd}")

    def _add_tab(self, tab: TerminalTab, title: str, tooltip: str) -> Adw.TabPage:
        page = self.tab_view.append(tab)
        page.set_title(title)
        page.set_tooltip(tooltip)
        tab.connect("process-exited", self._on_process_exited, page)
        tab.terminal.connect("contents-changed", self._on_terminal_output, page)
        self.tab_view.set_selected_page(page)
        self.content_stack.set_visible_child_name("tabs")
        self._apply_tab_status(page)
        GLib.idle_add(tab.grab_terminal_focus)
        return page

    def _apply_tab_status(self, page: Adw.TabPage) -> None:
        """Mirror the sidebar status dot onto the tab itself."""
        status = "attention" if page.get_needs_attention() else "open"
        page.set_icon(_status_icon(status))

    def _close_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _close_all_tabs(self) -> None:
        pages = [self.tab_view.get_nth_page(i) for i in range(self.tab_view.get_n_pages())]
        for page in pages:
            self.tab_view.close_page(page)

    def _close_confirmed(self, page: Adw.TabPage) -> None:
        """Force-close (terminate the child) — the graceful-close fallback."""
        self._confirmed_closes.add(page)
        self.tab_view.close_page(page)

    def _graceful_close(self, page: Adw.TabPage) -> None:
        """Ask Claude to exit cleanly (/exit), then close once the shell
        returns. Falls back to a force-close after a timeout."""
        tab = page.get_child()
        if not isinstance(tab, TerminalTab):
            self._close_confirmed(page)
            return
        self._closing_pages[page] = 0
        # Enter in a raw-mode TUI (claude) is carriage return, not newline.
        tab.feed_child_text("/exit\r")
        GLib.timeout_add(300, self._poll_graceful, page, tab)

    def _poll_graceful(self, page: Adw.TabPage, tab: TerminalTab) -> bool:
        if page not in self._closing_pages:
            return GLib.SOURCE_REMOVE  # already closed
        if not tab.has_running_command():
            tab.feed_child_text("exit\r")  # close the shell → child-exited closes the tab
            return GLib.SOURCE_REMOVE
        self._closing_pages[page] += 1
        if self._closing_pages[page] >= 40:  # ~12s safety net
            self._close_confirmed(page)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _sync_status(self, session_id: str) -> None:
        page = self._pages.get(session_id)
        if page is None:
            status = ""
        elif page.get_needs_attention():
            status = "attention"
        else:
            status = "open"
        self.store.set_status(session_id, status)
        self.sidebar.update_footer()

    def _session_id_of(self, page: Adw.TabPage) -> str | None:
        tab = page.get_child()
        if isinstance(tab, TerminalTab) and tab.session_id and not tab.fork:
            return tab.session_id
        return None

    def _on_terminal_output(self, _terminal, page: Adw.TabPage) -> None:
        if self.tab_view.get_selected_page() is page:
            return
        if not page.get_needs_attention():
            page.set_needs_attention(True)
            self._apply_tab_status(page)
            session_id = self._session_id_of(page)
            if session_id:
                self._sync_status(session_id)
        if self.state.get_setting("notify_idle"):
            self._schedule_idle_notify(page)

    def _on_selected_page_changed(self, view: Adw.TabView, _pspec) -> None:
        page = view.get_selected_page()
        if page is None:
            return
        self._cancel_idle(page)  # foreground now; no "finished" notification
        if page.get_needs_attention():
            page.set_needs_attention(False)
            self._apply_tab_status(page)
            session_id = self._session_id_of(page)
            if session_id:
                self._sync_status(session_id)
        if isinstance(page.get_child(), TerminalTab):
            GLib.idle_add(page.get_child().grab_terminal_focus)

    # -- idle notifications --------------------------------------------------

    def _schedule_idle_notify(self, page: Adw.TabPage) -> None:
        self._cancel_idle(page)
        self._idle_sources[page] = GLib.timeout_add(_IDLE_NOTIFY_MS, self._fire_idle_notify, page)

    def _cancel_idle(self, page: Adw.TabPage) -> None:
        source = self._idle_sources.pop(page, None)
        if source is not None:
            GLib.source_remove(source)

    def _fire_idle_notify(self, page: Adw.TabPage) -> bool:
        self._idle_sources.pop(page, None)
        if page is self.tab_view.get_selected_page() or not self.state.get_setting("notify_idle"):
            return GLib.SOURCE_REMOVE
        app = self.get_application()
        if app is not None:
            session_id = self._session_id_of(page) or ""
            notification = Gio.Notification.new(page.get_title())
            notification.set_body("Claude finished responding.")
            notification.set_default_action_and_target_value(
                "app.focus-session", GLib.Variant("s", session_id)
            )
            app.send_notification(session_id or page.get_title(), notification)
        return GLib.SOURCE_REMOVE

    def focus_session(self, session_id: str) -> None:
        page = self._pages.get(session_id)
        if page is not None:
            self.tab_view.set_selected_page(page)

    # -- tab rename / menu ---------------------------------------------------

    def _on_tab_setup_menu(self, _view: Adw.TabView, page: Adw.TabPage | None) -> None:
        if page is not None:
            self._menu_page = page

    def _rename_tab(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is None:
            return
        session_id = self._session_id_of(page)
        if session_id:  # real session tab → rename the session (syncs sidebar)
            session = self.store.get_session(session_id)
            if session is not None:
                self._prompt_rename_session(session)
            return
        # fork / new-session tab → local title rename only
        dialogs.rename_dialog(
            self,
            "Tab name",
            page.get_title(),
            lambda name: page.set_title(name.strip() or page.get_title()),
        )

    def _set_tab_emoji(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is None:
            return
        session_id = self._session_id_of(page)
        if session_id:
            current = self.state.get_emoji(session_id) or ""

            def save(emoji: str) -> None:
                self.state.set_emoji(session_id, emoji.strip())
                session = self.store.get_session(session_id)
                if session is not None:
                    page.set_title(self._tab_title(session))

            dialogs.emoji_dialog(self, current, save)
        else:  # fork / new tab: no persisted session, set a local prefix
            base = self._base_titles.get(page, page.get_title())
            self._base_titles[page] = base

            def save(emoji: str) -> None:
                emoji = emoji.strip()
                page.set_title(f"{emoji} {base}" if emoji else base)

            dialogs.emoji_dialog(self, "", save)

    def _copy_tab_session_id(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is None:
            return
        tab = page.get_child()
        if isinstance(tab, TerminalTab) and tab.session_id:
            self.get_clipboard().set(tab.session_id)

    def _close_menu_tab(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_process_exited(self, _tab: TerminalTab, _status: int, page: Adw.TabPage) -> None:
        self.tab_view.close_page(page)

    def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
        tab = page.get_child()
        if (
            isinstance(tab, TerminalTab)
            and page not in self._confirmed_closes
            and tab.has_running_command()
        ):
            if page not in self._closing_pages:  # start a graceful /exit in the background
                self._graceful_close(page)
            view.close_page_finish(page, False)  # keep the tab until it exits cleanly
            return True
        self._confirmed_closes.discard(page)
        self._closing_pages.pop(page, None)
        self._base_titles.pop(page, None)
        self._cancel_idle(page)
        session_id = self._session_id_of(page)
        if session_id:
            self._pages.pop(session_id, None)
            self._sync_status(session_id)
        view.close_page_finish(page, True)
        if view.get_n_pages() == 0:
            self.content_stack.set_visible_child_name("empty")
        return True  # we handled it

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
        cwd = session.cwd if session.cwd and Path(session.cwd).is_dir() else str(Path.home())
        subprocess.Popen(
            [_GHOSTTY, f"--working-directory={cwd}", "-e", "claude", "--resume", session.session_id],
            start_new_session=True,
        )

    def _on_rename_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is not None:
            self._prompt_rename_session(session)

    def _prompt_rename_session(self, session: Session) -> None:
        def save(name: str) -> None:
            self.store.rename(session.session_id, name)
            page = self._pages.get(session.session_id)
            if page is not None:
                page.set_title(self._tab_title(session))

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
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(session.jsonl_path)))
        launcher.open_containing_folder(self, None, None)

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
                dialogs.error_dialog(self, "Could not trash transcript", error)
                return
            page = self._pages.get(session.session_id)
            if page is not None:
                self.tab_view.close_page(page)

        dialogs.confirm_dialog(
            self,
            "Move transcript to trash?",
            f"“{self.store.display_name(session)}” will be removed from Claude's history.\n"
            "The file is moved to the trash and can be restored.",
            "Move to Trash",
            do_trash,
        )

    # -- preferences / about -------------------------------------------------

    def _show_about(self) -> None:
        about = Adw.AboutDialog(
            application_name="Claude Session Manager",
            application_icon="eu.zengo.ClaudeSessionManager",
            developer_name="Máté Molnár",
            version=__version__,
            license_type=Gtk.License.GPL_3_0,
            comments=(
                "Manage and resume Claude Code sessions.\n\n"
                "Unofficial community tool — not affiliated with or endorsed by Anthropic."
            ),
            website="https://github.com/r4nd3l/claude-session-manager",
            issue_url="https://github.com/r4nd3l/claude-session-manager/issues",
        )
        about.present(self)

    def _quick_switch(self) -> None:
        if self._switcher is not None:  # already open — don't stack another
            return
        self._switcher = QuickSwitcher(self.store, lambda item: self.open_session(item.session))
        self._switcher.connect("closed", lambda *_: setattr(self, "_switcher", None))
        self._switcher.present(self)

    def _show_preferences(self) -> None:
        PreferencesDialog(self.state, self._apply_settings_to_tabs).present(self)

    def _apply_settings_to_tabs(self) -> None:
        for i in range(self.tab_view.get_n_pages()):
            tab = self.tab_view.get_nth_page(i).get_child()
            if isinstance(tab, TerminalTab):
                tab.apply_settings(self.state.settings)
