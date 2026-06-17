"""Session sidebar: search, project accordion, favorites, selection mode.

Rows bind to SessionItem properties, so renames/stars/status changes update
in place; the list is only rebuilt when the store reports an order change.

Emits:
  open-session   (SessionItem, bool fork)
  open-many      (list[SessionItem])
  trash-many     (list[SessionItem])
"""

from __future__ import annotations

import shutil

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from .formatting import format_size
from .i18n import _
from .models import FAV_GROUP, SessionItem
from .providers import get_provider
from .store import SessionStore

_GHOSTTY = shutil.which("ghostty")
_ELLIPSIZE_END = 3  # Pango.EllipsizeMode.END


def _activate_win_action(widget: Gtk.Widget, action_name: str, session_id: str) -> None:
    """GTK3 doesn't have widget.activate_action(); look up from the window."""
    toplevel = widget.get_toplevel()
    if isinstance(toplevel, Gtk.ApplicationWindow):
        action = toplevel.lookup_action(action_name)
        if action is not None:
            action.activate(GLib.Variant("s", session_id))


class GroupHeaderRow(Gtk.ListBoxRow):
    """A real row acting as a group header."""

    def __init__(self, group_key: tuple, group_label: str, count: int, collapsed: bool) -> None:
        super().__init__()
        self.group_key = group_key
        self.set_selectable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.get_style_context().add_class("group-header")

        self._arrow = Gtk.Image()
        self._arrow.get_style_context().add_class("dim-label")
        box.pack_start(self._arrow, False, False, 0)

        icon_name = "starred-symbolic" if group_key == FAV_GROUP else "folder-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        icon.get_style_context().add_class("dim-label")
        box.pack_start(icon, False, False, 0)

        label = Gtk.Label(label=group_label.upper(), xalign=0.0)
        label.set_hexpand(True)
        label.get_style_context().add_class("dim-label")
        label.set_ellipsize(_ELLIPSIZE_END)
        box.pack_start(label, True, True, 0)

        count_label = Gtk.Label(label=str(count))
        count_label.get_style_context().add_class("count-badge")
        box.pack_start(count_label, False, False, 0)

        self.add(box)
        self.set_collapsed(collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        icon_name = "pan-end-symbolic" if collapsed else "pan-down-symbolic"
        self._arrow.set_from_icon_name(icon_name, Gtk.IconSize.MENU)


class SessionRow(Gtk.ListBoxRow):
    def __init__(self, item: SessionItem, sidebar: SessionSidebar) -> None:
        super().__init__()
        self.item = item
        self._sidebar = sidebar
        self.get_style_context().add_class("session-child")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(12)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.check = Gtk.CheckButton()
        self.check.set_valign(Gtk.Align.CENTER)
        self.check.set_no_show_all(True)
        self.check.set_visible(False)
        self.check.connect("toggled", lambda c: sidebar.on_row_check_toggled(self, c.get_active()))
        top.pack_start(self.check, False, False, 0)

        self.dot = Gtk.Box()
        self.dot.set_valign(Gtk.Align.CENTER)
        self.dot.get_style_context().add_class("status-dot")
        self.dot.set_size_request(8, 8)
        top.pack_start(self.dot, False, False, 0)

        agent_icon = Gtk.Image.new_from_icon_name(item.provider_icon, Gtk.IconSize.MENU)
        agent_icon.set_valign(Gtk.Align.CENTER)
        agent_icon.get_style_context().add_class("dim-label")
        agent_icon.set_tooltip_text(item.provider_label)
        top.pack_start(agent_icon, False, False, 0)

        self._name_label = Gtk.Label(xalign=0.0)
        self._name_label.set_hexpand(True)
        self._name_label.set_ellipsize(_ELLIPSIZE_END)
        self._name_label.get_style_context().add_class("heading")
        top.pack_start(self._name_label, True, True, 0)

        self._state_badge = Gtk.Image()
        self._state_badge.set_valign(Gtk.Align.CENTER)
        self._state_badge.set_no_show_all(True)
        top.pack_start(self._state_badge, False, False, 0)

        self._star_btn = Gtk.Button()
        self._star_btn.set_valign(Gtk.Align.CENTER)
        self._star_btn.get_style_context().add_class("flat")
        self._star_btn.connect(
            "clicked",
            lambda *_, sid=item.session_id: _activate_win_action(self, "toggle-favorite", sid),
        )
        top.pack_start(self._star_btn, False, False, 0)

        rename = Gtk.Button()
        rename.set_image(Gtk.Image.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON))
        rename.set_valign(Gtk.Align.CENTER)
        rename.get_style_context().add_class("flat")
        rename.set_tooltip_text(_("Rename session"))
        rename.connect(
            "clicked",
            lambda *_, sid=item.session_id: _activate_win_action(self, "rename-session", sid),
        )
        top.pack_start(rename, False, False, 0)
        box.pack_start(top, False, False, 0)

        self._subtitle_label = Gtk.Label(xalign=0.0)
        self._subtitle_label.set_ellipsize(_ELLIPSIZE_END)
        self._subtitle_label.get_style_context().add_class("dim-label")
        box.pack_start(self._subtitle_label, False, False, 0)

        self._preview_label = Gtk.Label(xalign=0.0)
        self._preview_label.set_ellipsize(_ELLIPSIZE_END)
        self._preview_label.get_style_context().add_class("dim-label")
        self._preview_label.set_no_show_all(True)
        box.pack_start(self._preview_label, False, False, 0)

        self.add(box)

        # Property bindings
        flags = GObject.BindingFlags.SYNC_CREATE
        item.bind_property("display-name", self._name_label, "label", flags)
        item.bind_property("subtitle", self._subtitle_label, "label", flags)
        item.bind_property("preview", self._preview_label, "label", flags)
        item.bind_property(
            "preview", self._preview_label, "visible", flags, lambda _b, value: bool(value)
        )
        item.bind_property(
            "favorite", self._star_btn, "label", flags,
            lambda _b, fav: "",
        )

        self._status_handler = item.connect("notify::status", self._on_status_changed)
        self._state_handler = item.connect("notify::state", self._on_state_changed)
        self._fav_handler = item.connect("notify::favorite", self._on_favorite_changed)
        self._on_status_changed(item, None)
        self._on_state_changed(item, None)
        self._on_favorite_changed(item, None)

        self.connect("button-press-event", self._on_button_press)

    def do_destroy(self) -> None:
        if self._status_handler is not None:
            self.item.disconnect(self._status_handler)
            self._status_handler = None
        if self._state_handler is not None:
            self.item.disconnect(self._state_handler)
            self._state_handler = None
        if self._fav_handler is not None:
            self.item.disconnect(self._fav_handler)
            self._fav_handler = None
        Gtk.ListBoxRow.do_destroy(self)

    def _on_favorite_changed(self, item: SessionItem, _pspec) -> None:
        icon_name = "starred-symbolic" if item.favorite else "non-starred-symbolic"
        self._star_btn.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        self._star_btn.set_tooltip_text(
            _("Remove from favorites") if item.favorite else _("Add to favorites")
        )

    def _on_status_changed(self, item: SessionItem, _pspec) -> None:
        ctx = self.dot.get_style_context()
        for css in ("open", "attention"):
            ctx.remove_class(css)
        if item.status:
            ctx.add_class(item.status)

    def _on_state_changed(self, item: SessionItem, _pspec) -> None:
        badge = self._state_badge
        ctx = badge.get_style_context()
        for css in ("waiting-badge", "interrupted-badge"):
            ctx.remove_class(css)
        if item.state == "waiting":
            badge.set_from_icon_name("dialog-question-symbolic", Gtk.IconSize.MENU)
            ctx.add_class("waiting-badge")
            badge.set_tooltip_text(_("Claude is waiting for your reply"))
            badge.set_visible(True)
        elif item.state == "interrupted":
            badge.set_from_icon_name("process-stop-symbolic", Gtk.IconSize.MENU)
            ctx.add_class("interrupted-badge")
            badge.set_tooltip_text(_("You interrupted Claude here"))
            badge.set_visible(True)
        else:
            badge.set_visible(False)

    def _on_button_press(self, _widget, event: Gdk.EventButton) -> bool:
        if event.button == 3:
            self._sidebar.show_row_menu(self, event.x, event.y)
            return True
        return False


class SessionSidebar(Gtk.Box):
    __gsignals__ = {
        "open-session": (GObject.SignalFlags.RUN_FIRST, None, (object, bool)),
        "open-many": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "trash-many": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, store: SessionStore) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class("cc-sidebar")
        self.store = store
        self._collapsed: set[tuple] = set()
        self._known_groups: set[tuple] = set()
        self._selection_mode = False
        self._selected: set[str] = set()
        self._rows: dict[str, SessionRow] = {}
        self._header_rows: dict[tuple, GroupHeaderRow] = {}
        self._store_handler: int | None = None

        self._store_handler = store.connect("refreshed", self._on_store_refreshed)

        # -- branded header -------------------------------------------------
        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        brand_box.get_style_context().add_class("cc-brand-box")

        brand_icon = Gtk.Image.new_from_icon_name(
            "utilities-terminal-symbolic", Gtk.IconSize.LARGE_TOOLBAR
        )
        brand_icon.get_style_context().add_class("cc-accent-icon")
        brand_box.pack_start(brand_icon, False, False, 0)

        brand_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand_title = Gtk.Label(label="Agent Session Manager", xalign=0.0)
        brand_title.get_style_context().add_class("cc-brand-title")
        brand_text.pack_start(brand_title, False, False, 0)
        brand_sub = Gtk.Label(label=_("Sessions"), xalign=0.0)
        brand_sub.get_style_context().add_class("cc-brand-sub")
        brand_text.pack_start(brand_sub, False, False, 0)
        brand_box.pack_start(brand_text, True, True, 0)

        menu = Gio.Menu()
        menu.append(_("Show hidden sessions"), "win.show-hidden")
        menu.append(_("MCP servers"), "win.mcp-servers")
        menu.append(_("Preferences"), "win.preferences")
        menu.append(_("About Agent Session Manager"), "win.about")
        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu_btn.get_style_context().add_class("flat")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu_btn.set_menu_model(menu)
        brand_box.pack_end(menu_btn, False, False, 0)

        self.pack_start(brand_box, False, False, 0)

        # -- toolbar row: select, search, refresh, collapse/expand -----------
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(6)

        self.select_btn = Gtk.ToggleButton()
        self.select_btn.set_image(Gtk.Image.new_from_icon_name("object-select-symbolic", Gtk.IconSize.MENU))
        self.select_btn.get_style_context().add_class("flat")
        self.select_btn.set_tooltip_text(_("Select sessions"))
        self.select_btn.connect("toggled", lambda b: self._set_selection_mode(b.get_active()))
        toolbar.pack_start(self.select_btn, False, False, 0)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search..."))
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", lambda *_: self._invalidate())
        toolbar.pack_start(self.search_entry, True, True, 0)

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU)
        refresh_btn.get_style_context().add_class("flat")
        refresh_btn.set_tooltip_text(_("Refresh session list"))
        refresh_btn.set_action_name("win.refresh")
        toolbar.pack_start(refresh_btn, False, False, 0)

        collapse_all = Gtk.Button.new_from_icon_name("pan-up-symbolic", Gtk.IconSize.MENU)
        collapse_all.get_style_context().add_class("flat")
        collapse_all.set_tooltip_text(_("Collapse all groups"))
        collapse_all.connect("clicked", lambda *_: self._set_all_collapsed(True))
        toolbar.pack_start(collapse_all, False, False, 0)

        expand_all = Gtk.Button.new_from_icon_name("pan-down-symbolic", Gtk.IconSize.MENU)
        expand_all.get_style_context().add_class("flat")
        expand_all.set_tooltip_text(_("Expand all groups"))
        expand_all.connect("clicked", lambda *_: self._set_all_collapsed(False))
        toolbar.pack_start(expand_all, False, False, 0)

        self.pack_start(toolbar, False, False, 0)

        # -- list ------------------------------------------------------------
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.get_style_context().add_class("navigation-sidebar")
        self.list.connect("row-activated", self._on_row_activated)
        self.list.set_filter_func(self._filter_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.list)

        # Empty state
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_vexpand(True)
        empty_icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.DIALOG)
        empty_icon.get_style_context().add_class("dim-label")
        empty_box.pack_start(empty_icon, False, False, 0)
        empty_title = Gtk.Label(label=f"<b>{_('No sessions found')}</b>")
        empty_title.set_use_markup(True)
        empty_box.pack_start(empty_title, False, False, 0)
        empty_desc = Gtk.Label(label=_("Run claude in a project directory first — "
            "sessions will appear here automatically."))
        empty_desc.set_line_wrap(True)
        empty_desc.set_max_width_chars(30)
        empty_desc.get_style_context().add_class("dim-label")
        empty_box.pack_start(empty_desc, False, False, 0)

        self._content_stack = Gtk.Stack()
        self._content_stack.add_named(scrolled, "list")
        self._content_stack.add_named(empty_box, "empty")
        self.pack_start(self._content_stack, True, True, 0)

        self.pack_start(self._build_action_bar(), False, False, 0)

        # -- status footer ----------------------------------------------------
        self.footer = Gtk.Label()
        self.footer.get_style_context().add_class("dim-label")
        self.footer.get_style_context().add_class("sidebar-footer")
        self.footer.set_ellipsize(_ELLIPSIZE_END)
        self.pack_start(self.footer, False, False, 0)

        if store.model.get_n_items():
            self._on_store_refreshed(store, True)

    def do_destroy(self) -> None:
        if self._store_handler is not None:
            self.store.disconnect(self._store_handler)
            self._store_handler = None
        Gtk.Box.do_destroy(self)

    # -- store sync ------------------------------------------------------------

    def _on_store_refreshed(self, store: SessionStore, order_changed: bool) -> None:
        self._selected &= set(store.sessions)
        if order_changed:
            self._rebuild_rows()
        self._update_selection_label()
        self._invalidate()
        self._content_stack.set_visible_child_name("empty" if not store.sessions else "list")
        self.update_footer()

    def update_footer(self) -> None:
        sessions = self.store.sessions.values()
        projects = {s.project_name for s in sessions}
        open_tabs = sum(
            1 for sid in self.store.sessions if (item := self.store.get_item(sid)) and item.status
        )
        parts = [
            _("{n} sessions").format(n=len(sessions)),
            _("{n} projects").format(n=len(projects)),
            format_size(sum(s.size for s in sessions)),
        ]
        if open_tabs:
            parts.append(_("{n} open").format(n=open_tabs))
        self.footer.set_label(" · ".join(parts))

    def _rebuild_rows(self) -> None:
        for child in self.list.get_children():
            self.list.remove(child)
        self._rows = {}
        self._header_rows = {}

        groups = []
        for i in range(self.store.model.get_n_items()):
            key = self.store.model.get_item(i).group_key
            if key not in groups:
                groups.append(key)
        for key in groups:
            if key not in self._known_groups:
                self._collapsed.add(key)
        self._known_groups = set(groups)

        previous_group: tuple | None = None
        for i in range(self.store.model.get_n_items()):
            item = self.store.model.get_item(i)
            if item.group_key != previous_group:
                header = GroupHeaderRow(
                    item.group_key,
                    _("Favorites") if item.group_key == FAV_GROUP else item.group_label,
                    self.store.group_counts.get(item.group_key, 0),
                    item.group_key in self._collapsed,
                )
                self._header_rows[item.group_key] = header
                self.list.add(header)
                previous_group = item.group_key
            row = SessionRow(item, self)
            self._rows[item.session_id] = row
            self.list.add(row)
        self.list.show_all()
        self._apply_selection_to_rows()

    def _apply_selection_to_rows(self) -> None:
        for row in self._rows.values():
            row.check.set_visible(self._selection_mode)
            row.check.set_active(row.item.session_id in self._selected)

    def focus_search(self) -> None:
        self.search_entry.grab_focus()

    # -- filtering / grouping ----------------------------------------------------

    def _invalidate(self) -> None:
        self.list.invalidate_filter()

    def _group_has_match(self, group_key: tuple, query: str) -> bool:
        for i in range(self.store.model.get_n_items()):
            item = self.store.model.get_item(i)
            if item.group_key == group_key and query in item.search_text:
                return True
        return False

    def _filter_row(self, row: Gtk.ListBoxRow) -> bool:
        query = self.search_entry.get_text().strip().lower()
        if isinstance(row, GroupHeaderRow):
            return self._group_has_match(row.group_key, query) if query else True
        if query:
            return query in row.item.search_text
        return row.item.group_key not in self._collapsed

    def _toggle_group(self, group_key: tuple) -> None:
        if group_key in self._collapsed:
            self._collapsed.discard(group_key)
        else:
            self._collapsed.add(group_key)
        header = self._header_rows.get(group_key)
        if header is not None:
            header.set_collapsed(group_key in self._collapsed)
        self._invalidate()

    def _set_all_collapsed(self, collapsed: bool) -> None:
        self._collapsed = set(self.store.group_counts) if collapsed else set()
        for group_key, header in self._header_rows.items():
            header.set_collapsed(group_key in self._collapsed)
        self._invalidate()

    # -- activation ----------------------------------------------------------

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if isinstance(row, GroupHeaderRow):
            self._toggle_group(row.group_key)
            return
        if self._selection_mode:
            row.check.set_active(not row.check.get_active())
            return
        self.emit("open-session", row.item, False)

    # -- context menu ------------------------------------------------------------

    def show_row_menu(self, row: SessionRow, x: float, y: float) -> None:
        session_id = row.item.session_id
        variant = GLib.Variant("s", session_id)

        def item(label: str, action: str) -> Gio.MenuItem:
            menu_item = Gio.MenuItem.new(label, None)
            menu_item.set_action_and_target_value(f"win.{action}", variant)
            return menu_item

        open_section = Gio.Menu()
        open_section.append_item(item(_("Open"), "open-session"))
        if _GHOSTTY:
            open_section.append_item(item(_("Open in Ghostty"), "open-ghostty"))
        if get_provider(row.item.session.provider).supports_fork:
            open_section.append_item(item(_("Fork session"), "fork-session"))

        edit_section = Gio.Menu()
        edit_section.append_item(item(_("Rename…"), "rename-session"))
        fav_label = (
            _("Remove from favorites") if self.store.state.is_favorite(session_id) else _("Add to favorites")
        )
        edit_section.append_item(item(fav_label, "toggle-favorite"))
        edit_section.append_item(item(_("Details…"), "session-details"))
        edit_section.append_item(item(_("Copy session ID"), "copy-session-id"))
        edit_section.append_item(item(_("Export as Markdown…"), "export-session"))
        edit_section.append_item(item(_("Reveal transcript"), "reveal-transcript"))

        danger_section = Gio.Menu()
        hide_label = _("Unhide session") if self.store.state.is_hidden(session_id) else _("Hide session")
        danger_section.append_item(item(hide_label, "hide-session"))
        danger_section.append_item(item(_("Move transcript to trash…"), "trash-session"))

        menu = Gio.Menu()
        menu.append_section(None, open_section)
        menu.append_section(None, edit_section)
        menu.append_section(None, danger_section)

        popover = Gtk.Popover.new_from_model(row, menu)
        toplevel = row.get_toplevel()
        if isinstance(toplevel, Gtk.ApplicationWindow):
            popover.insert_action_group("win", toplevel)
            app = toplevel.get_application()
            if app:
                popover.insert_action_group("app", app)
        popover.set_position(Gtk.PositionType.BOTTOM)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.connect("closed", lambda p: p.destroy())
        popover.popup()

    # -- selection mode ------------------------------------------------------------

    def _build_action_bar(self) -> Gtk.ActionBar:
        self.action_bar = Gtk.ActionBar()
        self.action_bar.set_no_show_all(True)
        self.action_bar.set_visible(False)

        self.sel_label = Gtk.Label(label="0 selected")
        self.sel_label.get_style_context().add_class("dim-label")
        self.action_bar.pack_start(self.sel_label)

        all_btn = Gtk.Button(label=_("All"))
        all_btn.get_style_context().add_class("flat")
        all_btn.set_tooltip_text(_("Select all (filtered) sessions"))
        all_btn.connect("clicked", lambda *_: self._select_all(True))
        self.action_bar.pack_start(all_btn)

        none_btn = Gtk.Button(label=_("None"))
        none_btn.get_style_context().add_class("flat")
        none_btn.set_tooltip_text(_("Clear selection"))
        none_btn.connect("clicked", lambda *_: self._select_all(False))
        self.action_bar.pack_start(none_btn)

        for icon, tooltip, callback in (
            ("user-trash-symbolic", _("Move selected transcripts to trash…"), self._bulk_trash),
            ("view-conceal-symbolic", _("Hide selected"), self._bulk_hide),
            ("non-starred-symbolic", _("Remove selected from favorites"), lambda: self._bulk_favorite(False)),
            ("starred-symbolic", _("Add selected to favorites"), lambda: self._bulk_favorite(True)),
            ("tab-new-symbolic", _("Open selected in tabs"), self._bulk_open),
        ):
            button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            button.get_style_context().add_class("flat")
            button.set_tooltip_text(tooltip)
            button.connect("clicked", lambda _b, cb=callback: cb())
            self.action_bar.pack_end(button)
        return self.action_bar

    def _set_selection_mode(self, active: bool) -> None:
        self._selection_mode = active
        if not active:
            self._selected.clear()
        self._apply_selection_to_rows()
        self.action_bar.set_visible(active)
        self._update_selection_label()

    def on_row_check_toggled(self, row: SessionRow, active: bool) -> None:
        if active:
            self._selected.add(row.item.session_id)
        else:
            self._selected.discard(row.item.session_id)
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        self.sel_label.set_label(f"{len(self._selected)} selected")

    def _select_all(self, selected: bool) -> None:
        for row in self._rows.values():
            if selected and not self._filter_row(row):
                continue
            row.check.set_active(selected)

    def _selected_items(self) -> list[SessionItem]:
        return [
            item for sid in self._selected if (item := self.store.get_item(sid)) is not None
        ]

    def _bulk_open(self) -> None:
        self.emit("open-many", self._selected_items())

    def _bulk_favorite(self, favorite: bool) -> None:
        self.store.set_favorites([i.session_id for i in self._selected_items()], favorite)

    def _bulk_hide(self) -> None:
        self.store.hide_many([i.session_id for i in self._selected_items()])

    def _bulk_trash(self) -> None:
        items = self._selected_items()
        if items:
            self.emit("trash-many", items)
