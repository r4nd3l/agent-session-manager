"""Main window: composes the session sidebar with the tabbed terminal area."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import __version__, dialogs
from .models import SessionItem
from .prefs import PreferencesDialog, apply_color_scheme
from .sessions import Session
from .sidebar import SessionSidebar
from .state import AppState
from .store import SessionStore
from .terminal import TerminalTab

_GHOSTTY = shutil.which("ghostty")


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

        self._install_actions()
        self._install_shortcuts()

        # --- content pane: header + tab bar + tab view ---
        self.tab_view = Adw.TabView()
        self.tab_view.connect("close-page", self._on_close_page)
        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)

        tab_bar = Adw.TabBar(view=self.tab_view)
        tab_bar.set_autohide(False)

        content_header = Adw.HeaderBar()
        new_btn = Gtk.Button(icon_name="tab-new-symbolic")
        new_btn.set_tooltip_text("New Claude session… (Ctrl+Shift+T)")
        new_btn.set_action_name("win.new-session")
        content_header.pack_start(new_btn)

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

        split = Adw.OverlaySplitView()
        split.set_sidebar(self.sidebar)
        split.set_content(content_view)
        split.set_min_sidebar_width(280)
        split.set_max_sidebar_width(400)
        self.set_content(split)

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
        title = self.store.display_name(session)
        page = self._add_tab(tab, f"{title} (fork)" if fork else title,
                             f"{session.project_name} — {session.session_id}")
        if not fork:
            self._pages[session.session_id] = page
            self._sync_status(session.session_id)

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
        GLib.idle_add(tab.grab_terminal_focus)
        return page

    def _close_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _sync_status(self, session_id: str) -> None:
        page = self._pages.get(session_id)
        if page is None:
            status = ""
        elif page.get_needs_attention():
            status = "attention"
        else:
            status = "open"
        self.store.set_status(session_id, status)

    def _session_id_of(self, page: Adw.TabPage) -> str | None:
        tab = page.get_child()
        if isinstance(tab, TerminalTab) and tab.session_id and not tab.fork:
            return tab.session_id
        return None

    def _on_terminal_output(self, _terminal, page: Adw.TabPage) -> None:
        if self.tab_view.get_selected_page() is not page and not page.get_needs_attention():
            page.set_needs_attention(True)
            session_id = self._session_id_of(page)
            if session_id:
                self._sync_status(session_id)

    def _on_selected_page_changed(self, view: Adw.TabView, _pspec) -> None:
        page = view.get_selected_page()
        if page is None:
            return
        if page.get_needs_attention():
            page.set_needs_attention(False)
            session_id = self._session_id_of(page)
            if session_id:
                self._sync_status(session_id)
        if isinstance(page.get_child(), TerminalTab):
            GLib.idle_add(page.get_child().grab_terminal_focus)

    def _on_process_exited(self, _tab: TerminalTab, _status: int, page: Adw.TabPage) -> None:
        self.tab_view.close_page(page)

    def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
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
        if session is None:
            return

        def save(name: str) -> None:
            self.store.rename(session.session_id, name)
            page = self._pages.get(session.session_id)
            if page is not None:
                page.set_title(self.store.display_name(session))

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
            # TODO: set website/issue_url once the GitHub repository exists
        )
        about.present(self)

    def _show_preferences(self) -> None:
        PreferencesDialog(self.state, self._apply_settings_to_tabs).present(self)

    def _apply_settings_to_tabs(self) -> None:
        for i in range(self.tab_view.get_n_pages()):
            tab = self.tab_view.get_nth_page(i).get_child()
            if isinstance(tab, TerminalTab):
                tab.apply_settings(self.state.settings)
