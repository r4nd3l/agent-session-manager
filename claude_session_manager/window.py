"""Main window: sidebar (favorites + project groups) + tabbed terminals."""

from __future__ import annotations

import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .prefs import PreferencesDialog, apply_color_scheme
from .sessions import CLAUDE_PROJECTS_DIR, Session, SessionDetails, discover_sessions, parse_details
from .state import AppState
from .terminal import TerminalTab

_GHOSTTY = shutil.which("ghostty")

_FAV_GROUP = ("fav", "")


def _relative_time(dt: datetime) -> str:
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 7 * 86400:
        return f"{seconds // 86400}d ago"
    return dt.strftime("%Y-%m-%d")


def _format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} B"


def _format_timestamp(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


class SessionRow(Gtk.ListBoxRow):
    def __init__(self, session: Session, display_name: str, favorite: bool, group_key: tuple, group_label: str) -> None:
        super().__init__()
        self.session = session
        self.group_key = group_key
        self.group_label = group_label
        self.search_text = " ".join(
            (display_name, session.project_name, session.preview, session.session_id)
        ).lower()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.check = Gtk.CheckButton(valign=Gtk.Align.CENTER, visible=False)
        self.check.connect("toggled", self._on_check_toggled)
        top.append(self.check)

        self.dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self.dot.add_css_class("status-dot")
        top.append(self.dot)

        self.name_label = Gtk.Label(label=display_name, xalign=0.0)
        self.name_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self.name_label.set_hexpand(True)
        self.name_label.add_css_class("heading")
        top.append(self.name_label)

        star = Gtk.Button(icon_name="starred-symbolic" if favorite else "non-starred-symbolic")
        star.set_valign(Gtk.Align.CENTER)
        star.add_css_class("flat")
        star.set_tooltip_text("Remove from favorites" if favorite else "Add to favorites")
        star.connect("clicked", lambda *_: self.activate_action("win.toggle-favorite", GLib.Variant("s", session.session_id)))
        top.append(star)

        rename = Gtk.Button(icon_name="document-edit-symbolic")
        rename.set_valign(Gtk.Align.CENTER)
        rename.add_css_class("flat")
        rename.set_tooltip_text("Rename session")
        rename.connect("clicked", lambda *_: self.activate_action("win.rename-session", GLib.Variant("s", session.session_id)))
        top.append(rename)
        box.append(top)

        subtitle = Gtk.Label(
            label=f"{session.project_name} · {_relative_time(session.last_active)}",
            xalign=0.0,
        )
        subtitle.set_ellipsize(3)
        subtitle.add_css_class("dim-label")
        subtitle.add_css_class("caption")
        box.append(subtitle)

        if session.preview:
            preview = Gtk.Label(label=session.preview, xalign=0.0)
            preview.set_ellipsize(3)
            preview.add_css_class("dim-label")
            preview.add_css_class("caption")
            box.append(preview)

        self.set_child(box)

        right_click = Gtk.GestureClick(button=3)
        right_click.connect("pressed", self._on_right_click)
        self.add_controller(right_click)

    def _on_right_click(self, _gesture, _n_press: int, x: float, y: float) -> None:
        window = self.get_root()
        if isinstance(window, MainWindow):
            window.show_row_menu(self, x, y)

    def _on_check_toggled(self, check: Gtk.CheckButton) -> None:
        window = self.get_root()
        if isinstance(window, MainWindow):
            window.on_row_selection_changed(self.session.session_id, check.get_active())

    def set_selection_mode(self, active: bool, selected: bool) -> None:
        self.check.set_visible(active)
        self.check.set_active(selected)

    def set_status(self, status: str | None) -> None:
        """status: 'open', 'attention', or None (idle)."""
        for css in ("open", "attention"):
            self.dot.remove_css_class(css)
        if status:
            self.dot.add_css_class(status)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Claude Session Manager")
        self.set_icon_name("eu.zengo.ClaudeSessionManager")
        self.set_default_size(1280, 800)

        self.state = AppState()
        apply_color_scheme(self.state.get_setting("color_scheme"))

        self._sessions: dict[str, Session] = {}
        self._pages: dict[str, Adw.TabPage] = {}  # session_id -> open tab
        self._rows: dict[str, SessionRow] = {}
        self._collapsed: set[tuple] = set()
        self._monitors: list[Gio.FileMonitor] = []
        self._refresh_pending = False
        self._selection_mode = False
        self._selected: set[str] = set()

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

        self.placeholder = Adw.StatusPage(
            icon_name="utilities-terminal-symbolic",
            title="No session open",
            description="Pick a session from the sidebar, or start a new one.",
        )

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(self.placeholder, "empty")
        self.content_stack.add_named(self.tab_view, "tabs")

        content_view = Adw.ToolbarView()
        content_view.add_top_bar(content_header)
        content_view.add_top_bar(tab_bar)
        content_view.set_content(self.content_stack)

        # --- sidebar: header + search + session list ---
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_title_widget(Adw.WindowTitle(title="Sessions"))

        self.select_btn = Gtk.ToggleButton(icon_name="object-select-symbolic")
        self.select_btn.set_tooltip_text("Select sessions")
        self.select_btn.connect("toggled", lambda b: self._set_selection_mode(b.get_active()))
        sidebar_header.pack_start(self.select_btn)

        menu = Gio.Menu()
        menu.append("Show hidden sessions", "win.show-hidden")
        menu.append("Preferences", "win.preferences")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        sidebar_header.pack_end(menu_btn)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh session list")
        refresh_btn.set_action_name("win.refresh")
        sidebar_header.pack_end(refresh_btn)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search sessions…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", lambda *_: self._invalidate_list())

        collapse_all = Gtk.Button(icon_name="pan-up-symbolic")
        collapse_all.add_css_class("flat")
        collapse_all.set_tooltip_text("Collapse all groups")
        collapse_all.set_action_name("win.collapse-all")

        expand_all = Gtk.Button(icon_name="pan-down-symbolic")
        expand_all.add_css_class("flat")
        expand_all.set_tooltip_text("Expand all groups")
        expand_all.set_action_name("win.expand-all")

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        search_box.set_margin_start(8)
        search_box.set_margin_end(8)
        search_box.set_margin_bottom(6)
        search_box.append(self.search_entry)
        search_box.append(collapse_all)
        search_box.append(expand_all)

        self.session_list = Gtk.ListBox()
        self.session_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.session_list.add_css_class("navigation-sidebar")
        self.session_list.connect("row-activated", self._on_row_activated)
        self.session_list.set_filter_func(self._filter_row)
        self.session_list.set_header_func(self._header_func)

        scrolled = Gtk.ScrolledWindow(child=self.session_list)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        sidebar_view = Adw.ToolbarView()
        sidebar_view.add_top_bar(sidebar_header)
        sidebar_view.add_top_bar(search_box)
        sidebar_view.set_content(scrolled)
        sidebar_view.add_bottom_bar(self._build_action_bar())

        # --- split view ---
        split = Adw.OverlaySplitView()
        split.set_sidebar(sidebar_view)
        split.set_content(content_view)
        split.set_min_sidebar_width(280)
        split.set_max_sidebar_width(400)
        self.set_content(split)

        self.refresh_sessions()
        self._setup_monitors()

    # -- actions / shortcuts -------------------------------------------------

    def _install_actions(self) -> None:
        plain = {
            "refresh": lambda *_: self.refresh_sessions(),
            "new-session": lambda *_: self._new_session(),
            "preferences": lambda *_: self._show_preferences(),
            "focus-search": lambda *_: self.search_entry.grab_focus(),
            "close-tab": lambda *_: self._close_current_tab(),
            "next-tab": lambda *_: self.tab_view.select_next_page(),
            "prev-tab": lambda *_: self.tab_view.select_previous_page(),
            "collapse-all": lambda *_: self._set_all_collapsed(True),
            "expand-all": lambda *_: self._set_all_collapsed(False),
        }
        for name, cb in plain.items():
            action = Gio.SimpleAction(name=name)
            action.connect("activate", cb)
            self.add_action(action)

        per_session = {
            "open-session": self._on_open_action,
            "fork-session": self._on_fork_action,
            "open-ghostty": self._on_open_ghostty,
            "rename-session": self._on_rename_action,
            "toggle-favorite": self._on_toggle_favorite,
            "copy-session-id": self._on_copy_session_id,
            "reveal-transcript": self._on_reveal_transcript,
            "session-details": self._on_session_details,
            "hide-session": self._on_hide_session,
            "trash-session": self._on_trash_session,
        }
        for name, cb in per_session.items():
            action = Gio.SimpleAction(name=name, parameter_type=GLib.VariantType("s"))
            action.connect("activate", cb)
            self.add_action(action)

        show_hidden = Gio.SimpleAction.new_stateful("show-hidden", None, GLib.Variant.new_boolean(False))
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
                    Gtk.ShortcutTrigger.parse_string(trigger),
                    Gtk.NamedAction.new(action),
                )
            )
        self.add_controller(controller)

    # -- selection mode ------------------------------------------------------

    def _build_action_bar(self) -> Gtk.ActionBar:
        self.action_bar = Gtk.ActionBar()
        self.action_bar.set_revealed(False)

        self.sel_label = Gtk.Label(label="0 selected")
        self.sel_label.add_css_class("dim-label")
        self.action_bar.pack_start(self.sel_label)

        all_btn = Gtk.Button(label="All")
        all_btn.add_css_class("flat")
        all_btn.set_tooltip_text("Select all (filtered) sessions")
        all_btn.connect("clicked", lambda *_: self._select_all(True))
        self.action_bar.pack_start(all_btn)

        none_btn = Gtk.Button(label="None")
        none_btn.add_css_class("flat")
        none_btn.set_tooltip_text("Clear selection")
        none_btn.connect("clicked", lambda *_: self._select_all(False))
        self.action_bar.pack_start(none_btn)

        for icon, tooltip, callback in (
            ("user-trash-symbolic", "Move selected transcripts to trash…", self._bulk_trash),
            ("view-conceal-symbolic", "Hide selected", self._bulk_hide),
            ("non-starred-symbolic", "Remove selected from favorites", lambda: self._bulk_favorite(False)),
            ("starred-symbolic", "Add selected to favorites", lambda: self._bulk_favorite(True)),
            ("tab-new-symbolic", "Open selected in tabs", self._bulk_open),
        ):
            button = Gtk.Button(icon_name=icon)
            button.add_css_class("flat")
            button.set_tooltip_text(tooltip)
            button.connect("clicked", lambda _b, cb=callback: cb())
            self.action_bar.pack_end(button)
        return self.action_bar

    def _set_selection_mode(self, active: bool) -> None:
        self._selection_mode = active
        if not active:
            self._selected.clear()
        for row in self._rows.values():
            row.set_selection_mode(active, row.session.session_id in self._selected)
        self.action_bar.set_revealed(active)
        self._update_selection_label()

    def on_row_selection_changed(self, session_id: str, selected: bool) -> None:
        if selected:
            self._selected.add(session_id)
        else:
            self._selected.discard(session_id)
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        self.sel_label.set_label(f"{len(self._selected)} selected")

    def _select_all(self, selected: bool) -> None:
        for row in self._rows.values():
            if selected and not self._filter_row(row):
                continue  # respect the current search filter
            row.check.set_active(selected)

    def _selected_sessions(self) -> list[Session]:
        return [self._sessions[sid] for sid in self._selected if sid in self._sessions]

    def _bulk_open(self) -> None:
        for session in self._selected_sessions():
            self.open_session(session)

    def _bulk_favorite(self, favorite: bool) -> None:
        for session in self._selected_sessions():
            if self.state.is_favorite(session.session_id) != favorite:
                self.state.toggle_favorite(session.session_id)
        self.refresh_sessions()

    def _bulk_hide(self) -> None:
        for session in self._selected_sessions():
            self.state.set_hidden(session.session_id, True)
        self.refresh_sessions()

    def _bulk_trash(self) -> None:
        sessions = self._selected_sessions()
        if not sessions:
            return
        dialog = Adw.AlertDialog(
            heading=f"Move {len(sessions)} transcript(s) to trash?",
            body="The files are moved to the trash and can be restored.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("trash", "Move to Trash")
        dialog.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", self._on_bulk_trash_response, sessions)
        dialog.present(self)

    def _on_bulk_trash_response(self, _dialog, response: str, sessions: list[Session]) -> None:
        if response != "trash":
            return
        errors = []
        for session in sessions:
            try:
                Gio.File.new_for_path(str(session.jsonl_path)).trash(None)
            except GLib.Error as err:
                errors.append(f"{self._display_name(session)}: {err.message}")
                continue
            self._selected.discard(session.session_id)
            page = self._pages.get(session.session_id)
            if page is not None:
                self.tab_view.close_page(page)
        self.refresh_sessions()
        if errors:
            error = Adw.AlertDialog(heading="Some transcripts could not be trashed", body="\n".join(errors))
            error.add_response("ok", "OK")
            error.present(self)

    # -- sidebar -----------------------------------------------------------

    def refresh_sessions(self) -> None:
        show_hidden = self.lookup_action("show-hidden").get_state().get_boolean()
        sessions = discover_sessions()
        self._sessions = {s.session_id: s for s in sessions}

        visible = [s for s in sessions if show_hidden or not self.state.is_hidden(s.session_id)]
        favorites = [s for s in visible if self.state.is_favorite(s.session_id)]
        rest = [s for s in visible if not self.state.is_favorite(s.session_id)]

        # Projects ordered by their most recent session (input is mtime-sorted)
        grouped: dict[tuple, list[Session]] = {}
        for session in rest:
            grouped.setdefault(("proj", session.project_name), []).append(session)

        self.session_list.remove_all()
        self._rows = {}
        self._group_counts: dict[tuple, int] = {}

        def add_row(session: Session, group_key: tuple, group_label: str) -> None:
            name = self._display_name(session)
            row = SessionRow(session, name, self.state.is_favorite(session.session_id), group_key, group_label)
            self._rows[session.session_id] = row
            self.session_list.append(row)
            self._group_counts[group_key] = self._group_counts.get(group_key, 0) + 1

        for session in favorites:
            add_row(session, _FAV_GROUP, "Favorites")
        for (key, sessions_in_project) in grouped.items():
            for session in sessions_in_project:
                add_row(session, key, key[1])

        self._selected &= set(self._sessions)  # drop selections for vanished sessions
        if self._selection_mode:
            for row in self._rows.values():
                row.set_selection_mode(True, row.session.session_id in self._selected)
            self._update_selection_label()

        self._update_row_statuses()
        self._invalidate_list()

    def _display_name(self, session: Session) -> str:
        return self.state.get_name(session.session_id) or session.preview or session.session_id[:8]

    def _invalidate_list(self) -> None:
        self.session_list.invalidate_filter()
        self.session_list.invalidate_headers()

    def _filter_row(self, row: SessionRow) -> bool:
        query = self.search_entry.get_text().strip().lower()
        if query:
            return query in row.search_text  # search ignores collapsed state
        return row.group_key not in self._collapsed

    def _header_func(self, row: SessionRow, before: SessionRow | None) -> None:
        if before is not None and before.group_key == row.group_key:
            row.set_header(None)
            return
        collapsed = row.group_key in self._collapsed
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.add_css_class("group-header")
        arrow = Gtk.Image.new_from_icon_name("pan-end-symbolic" if collapsed else "pan-down-symbolic")
        arrow.add_css_class("dim-label")
        header.append(arrow)
        if row.group_key == _FAV_GROUP:
            icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            icon.add_css_class("dim-label")
            header.append(icon)
        label = Gtk.Label(label=row.group_label, xalign=0.0)
        label.add_css_class("heading")
        label.set_hexpand(True)
        label.set_ellipsize(3)
        header.append(label)
        count = Gtk.Label(label=str(self._group_counts.get(row.group_key, 0)))
        count.add_css_class("dim-label")
        count.add_css_class("caption")
        header.append(count)

        click = Gtk.GestureClick()
        click.connect("pressed", self._on_header_clicked, row.group_key)
        header.add_controller(click)
        row.set_header(header)

    def _set_all_collapsed(self, collapsed: bool) -> None:
        if collapsed:
            self._collapsed = set(self._group_counts)
        else:
            self._collapsed.clear()
        self._invalidate_list()

    def _on_header_clicked(self, _gesture, _n, _x, _y, group_key: tuple) -> None:
        if group_key in self._collapsed:
            self._collapsed.discard(group_key)
        else:
            self._collapsed.add(group_key)
        self._invalidate_list()

    def _on_row_activated(self, _list: Gtk.ListBox, row: SessionRow) -> None:
        if self._selection_mode:
            row.check.set_active(not row.check.get_active())
            return
        self.open_session(row.session)

    def _update_row_statuses(self) -> None:
        for session_id, row in self._rows.items():
            page = self._pages.get(session_id)
            if page is None:
                row.set_status(None)
            elif page.get_needs_attention():
                row.set_status("attention")
            else:
                row.set_status("open")

    # -- live updates --------------------------------------------------------

    def _setup_monitors(self) -> None:
        for monitor in self._monitors:
            monitor.cancel()
        self._monitors = []
        paths = [CLAUDE_PROJECTS_DIR]
        try:
            paths += [p for p in CLAUDE_PROJECTS_DIR.iterdir() if p.is_dir()]
        except OSError:
            pass
        for path in paths:
            try:
                monitor = Gio.File.new_for_path(str(path)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
            except GLib.Error:
                continue
            monitor.connect("changed", self._on_fs_event)
            self._monitors.append(monitor)

    def _on_fs_event(self, _monitor, _file, _other, _event) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        GLib.timeout_add(2000, self._debounced_refresh)

    def _debounced_refresh(self) -> bool:
        self._refresh_pending = False
        self.refresh_sessions()
        self._setup_monitors()  # pick up new project dirs
        return GLib.SOURCE_REMOVE

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
        page = self.tab_view.append(tab)
        title = self._display_name(session)
        page.set_title(f"{title} (fork)" if fork else title)
        page.set_tooltip(f"{session.project_name} — {session.session_id}")
        if not fork:
            self._pages[session.session_id] = page
        tab.connect("process-exited", self._on_process_exited, page)
        tab.terminal.connect("contents-changed", self._on_terminal_output, page)

        self.tab_view.set_selected_page(page)
        self.content_stack.set_visible_child_name("tabs")
        GLib.idle_add(tab.grab_terminal_focus)
        self._update_row_statuses()

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
        page = self.tab_view.append(tab)
        page.set_title(GLib.path_get_basename(cwd))
        page.set_tooltip(f"new session — {cwd}")
        tab.connect("process-exited", self._on_process_exited, page)
        tab.terminal.connect("contents-changed", self._on_terminal_output, page)
        self.tab_view.set_selected_page(page)
        self.content_stack.set_visible_child_name("tabs")
        GLib.idle_add(tab.grab_terminal_focus)

    def _close_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_terminal_output(self, _terminal, page: Adw.TabPage) -> None:
        if self.tab_view.get_selected_page() is not page and not page.get_needs_attention():
            page.set_needs_attention(True)
            self._update_row_statuses()

    def _on_selected_page_changed(self, view: Adw.TabView, _pspec) -> None:
        page = view.get_selected_page()
        if page is not None and page.get_needs_attention():
            page.set_needs_attention(False)
            self._update_row_statuses()
        if page is not None and isinstance(page.get_child(), TerminalTab):
            GLib.idle_add(page.get_child().grab_terminal_focus)

    def _on_process_exited(self, tab: TerminalTab, _status: int, page: Adw.TabPage) -> None:
        self.tab_view.close_page(page)

    def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
        tab = page.get_child()
        if isinstance(tab, TerminalTab) and tab.session_id and not tab.fork:
            self._pages.pop(tab.session_id, None)
        view.close_page_finish(page, True)
        if view.get_n_pages() == 0:
            self.content_stack.set_visible_child_name("empty")
        self._update_row_statuses()
        return True  # we handled it

    # -- context menu --------------------------------------------------------

    def show_row_menu(self, row: SessionRow, x: float, y: float) -> None:
        session_id = row.session.session_id
        variant = GLib.Variant("s", session_id)

        def item(label: str, action: str) -> Gio.MenuItem:
            menu_item = Gio.MenuItem.new(label, None)
            menu_item.set_action_and_target_value(f"win.{action}", variant)
            return menu_item

        open_section = Gio.Menu()
        open_section.append_item(item("Open", "open-session"))
        if _GHOSTTY:
            open_section.append_item(item("Open in Ghostty", "open-ghostty"))
        open_section.append_item(item("Fork session", "fork-session"))

        edit_section = Gio.Menu()
        edit_section.append_item(item("Rename…", "rename-session"))
        fav_label = "Remove from favorites" if self.state.is_favorite(session_id) else "Add to favorites"
        edit_section.append_item(item(fav_label, "toggle-favorite"))
        edit_section.append_item(item("Details…", "session-details"))
        edit_section.append_item(item("Copy session ID", "copy-session-id"))
        edit_section.append_item(item("Reveal transcript", "reveal-transcript"))

        danger_section = Gio.Menu()
        hide_label = "Unhide session" if self.state.is_hidden(session_id) else "Hide session"
        danger_section.append_item(item(hide_label, "hide-session"))
        danger_section.append_item(item("Move transcript to trash…", "trash-session"))

        menu = Gio.Menu()
        menu.append_section(None, open_section)
        menu.append_section(None, edit_section)
        menu.append_section(None, danger_section)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(row)
        popover.set_has_arrow(False)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.connect("closed", lambda p: GLib.idle_add(p.unparent))
        popover.popup()

    # -- per-session actions ---------------------------------------------------

    def _session_for(self, param: GLib.Variant) -> Session | None:
        return self._sessions.get(param.get_string())

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

    def _on_toggle_favorite(self, _action, param: GLib.Variant) -> None:
        self.state.toggle_favorite(param.get_string())
        self.refresh_sessions()

    def _on_copy_session_id(self, _action, param: GLib.Variant) -> None:
        self.get_clipboard().set(param.get_string())

    def _on_reveal_transcript(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(session.jsonl_path)))
        launcher.open_containing_folder(self, None, None)

    def _on_hide_session(self, _action, param: GLib.Variant) -> None:
        session_id = param.get_string()
        self.state.set_hidden(session_id, not self.state.is_hidden(session_id))
        self.refresh_sessions()

    def _on_show_hidden(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.refresh_sessions()

    def _on_trash_session(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return
        dialog = Adw.AlertDialog(
            heading="Move transcript to trash?",
            body=f"“{self._display_name(session)}” will be removed from Claude's history.\n"
            f"The file is moved to the trash and can be restored.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("trash", "Move to Trash")
        dialog.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", self._on_trash_response, session)
        dialog.present(self)

    def _on_trash_response(self, _dialog, response: str, session: Session) -> None:
        if response != "trash":
            return
        try:
            Gio.File.new_for_path(str(session.jsonl_path)).trash(None)
        except GLib.Error as err:
            error = Adw.AlertDialog(heading="Could not trash transcript", body=err.message)
            error.add_response("ok", "OK")
            error.present(self)
            return
        page = self._pages.get(session.session_id)
        if page is not None:
            self.tab_view.close_page(page)
        self.refresh_sessions()

    # -- details dialog --------------------------------------------------------

    def _on_session_details(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return

        group = Adw.PreferencesGroup()
        spinner_row = Adw.ActionRow(title="Reading transcript…")
        spinner = Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER)
        spinner_row.add_suffix(spinner)
        group.add(spinner_row)

        page = Adw.PreferencesPage()
        page.add(group)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=self._display_name(session), subtitle=session.project_name))
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(page)

        dialog = Adw.Dialog(title="Session details")
        dialog.set_content_width(480)
        dialog.set_content_height(560)
        dialog.set_child(view)
        dialog.present(self)

        def work() -> None:
            details = parse_details(session.jsonl_path)
            GLib.idle_add(populate, details)

        def populate(details: SessionDetails) -> bool:
            page.remove(group)
            info = Adw.PreferencesGroup()

            def add(title: str, value: str) -> None:
                action_row = Adw.ActionRow(title=title, subtitle=value)
                action_row.add_css_class("property")
                info.add(action_row)

            add("Session ID", session.session_id)
            add("Directory", session.cwd or "unknown")
            add("Created", _format_timestamp(details.first_timestamp))
            add("Last activity", _format_timestamp(details.last_timestamp))
            add("Messages", f"{details.user_messages} user · {details.assistant_messages} assistant")
            add("Tool calls", str(details.tool_calls))
            add("Models", ", ".join(details.models) or "—")
            add(
                "Tokens",
                f"{_format_tokens(details.input_tokens)} in · "
                f"{_format_tokens(details.output_tokens)} out · "
                f"{_format_tokens(details.cache_read_tokens)} cache-read",
            )
            add("Transcript size", _format_size(details.file_size))
            page.add(info)
            return GLib.SOURCE_REMOVE

        threading.Thread(target=work, daemon=True).start()

    # -- renaming ----------------------------------------------------------

    def _on_rename_action(self, _action, param: GLib.Variant) -> None:
        session_id = param.get_string()
        session = self._sessions.get(session_id)
        if session is None:
            return
        current = self.state.get_name(session_id) or ""

        dialog = Adw.AlertDialog(
            heading="Rename session",
            body=session.preview or session_id,
        )
        entry = Gtk.Entry(text=current, placeholder_text="Custom name")
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.connect("response", self._on_rename_response, session_id, entry)
        dialog.present(self)

    def _on_rename_response(self, _dialog, response: str, session_id: str, entry: Gtk.Entry) -> None:
        if response != "save":
            return
        self.state.set_name(session_id, entry.get_text())
        self.refresh_sessions()
        page = self._pages.get(session_id)
        if page is not None:
            session = self._sessions.get(session_id)
            if session is not None:
                page.set_title(self._display_name(session))

    # -- preferences -------------------------------------------------------

    def _show_preferences(self) -> None:
        PreferencesDialog(self.state, self._apply_settings_to_tabs).present(self)

    def _apply_settings_to_tabs(self) -> None:
        for i in range(self.tab_view.get_n_pages()):
            tab = self.tab_view.get_nth_page(i).get_child()
            if isinstance(tab, TerminalTab):
                tab.apply_settings(self.state.settings)
