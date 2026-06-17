"""Quick switcher: a type-ahead dialog to jump to any session."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from .models import SessionItem
from .store import SessionStore

_MAX_RESULTS = 50
_ELLIPSIZE_END = 3  # Pango.EllipsizeMode.END


class QuickSwitcher(Gtk.Window):
    def __init__(self, store: SessionStore, on_choose: Callable[[SessionItem], None],
                 parent: Gtk.Window | None = None) -> None:
        super().__init__(
            title="Switch session",
            type=Gtk.WindowType.TOPLEVEL,
            default_width=560,
            default_height=460,
        )
        self._store = store
        self._on_choose = on_choose
        self.set_modal(True)
        if parent is not None:
            self.set_transient_for(parent)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self._entry = Gtk.SearchEntry()
        self._entry.get_style_context().add_class("switcher-entry")
        self._entry.set_placeholder_text("Jump to a session...")
        self._entry.set_margin_top(12)
        self._entry.set_margin_start(12)
        self._entry.set_margin_end(12)
        self._entry.set_margin_bottom(4)
        self._entry.connect("search-changed", lambda *_: self._refilter())
        self._entry.connect("activate", lambda *_: self._activate_selected())

        self._entry.connect("key-press-event", self._on_key)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.get_style_context().add_class("navigation-sidebar")
        self._list.connect("row-activated", lambda _l, row: self._choose(row))

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self._list)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.pack_start(self._entry, False, False, 0)
        box.pack_start(sep, False, False, 0)
        box.pack_start(scrolled, True, True, 0)
        self.add(box)

        self.connect("map", lambda *_: self._entry.grab_focus())
        self.connect("delete-event", lambda *_: self._on_close())
        self._refilter()

    def present_switcher(self, parent: Gtk.Window | None = None) -> None:
        if parent is not None:
            self.set_transient_for(parent)
        self.show_all()
        self.present()

    def _on_close(self) -> bool:
        self.destroy()
        return True

    # -- building / filtering ------------------------------------------------

    def _refilter(self) -> None:
        for child in self._list.get_children():
            self._list.remove(child)
        query = self._entry.get_text().strip().lower()
        model = self._store.model
        shown = 0
        for i in range(model.get_n_items()):
            item = model.get_item(i)
            if query and query not in item.search_text:
                continue
            self._list.add(self._make_row(item))
            shown += 1
            if shown >= _MAX_RESULTS:
                break
        self._list.show_all()
        first = self._list.get_row_at_index(0)
        if first is not None:
            self._list.select_row(first)

    def _make_row(self, item: SessionItem) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.item = item
        row.get_style_context().add_class("switcher-row")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        name = Gtk.Label(label=item.display_name, xalign=0.0)
        name.get_style_context().add_class("heading")
        name.set_ellipsize(_ELLIPSIZE_END)
        box.pack_start(name, False, False, 0)

        subtitle = item.session.project_name
        if item.session.preview:
            subtitle += f" · {item.session.preview}"
        sub = Gtk.Label(label=subtitle, xalign=0.0)
        sub.get_style_context().add_class("dim-label")
        sub.set_ellipsize(_ELLIPSIZE_END)
        box.pack_start(sub, False, False, 0)

        row.add(box)
        return row

    # -- navigation ----------------------------------------------------------

    def _on_key(self, _widget, event: Gdk.EventKey) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_Down:
            self._move(1)
            return True
        if keyval == Gdk.KEY_Up:
            self._move(-1)
            return True
        if keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def _move(self, delta: int) -> None:
        selected = self._list.get_selected_row()
        index = selected.get_index() if selected is not None else -1
        target = self._list.get_row_at_index(index + delta)
        if target is not None:
            self._list.select_row(target)
            target.grab_focus()
            self._entry.grab_focus()

    # -- choosing ------------------------------------------------------------

    def _activate_selected(self) -> None:
        self._choose(self._list.get_selected_row())

    def _choose(self, row: Gtk.ListBoxRow | None) -> None:
        if row is not None and getattr(row, "item", None) is not None:
            self._on_choose(row.item)
            self.destroy()
