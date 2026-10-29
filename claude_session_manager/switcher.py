"""Quick switcher: a type-ahead dialog to jump to a session (history) or
to a running agent (the goto picker)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

_MAX_RESULTS = 50
_ELLIPSIZE_END = 3  # Pango.EllipsizeMode.END


@dataclass
class SwitchEntry:
    title: str
    subtitle: str
    payload: object  # handed to on_choose
    search_text: str = ""  # defaults to title + subtitle
    state: str = ""  # agent-state dot ("" = none)


class QuickSwitcher(Adw.Dialog):
    def __init__(self, entries: list[SwitchEntry], on_choose: Callable[[object], None],
                 title: str, placeholder: str) -> None:
        super().__init__(title=title)
        self._entries = entries
        self._on_choose = on_choose
        self.set_content_width(560)
        self.set_content_height(460)
        self.set_follows_content_size(False)

        self._entry = Gtk.SearchEntry(placeholder_text=placeholder)
        self._entry.set_margin_top(10)
        self._entry.set_margin_start(10)
        self._entry.set_margin_end(10)
        self._entry.connect("search-changed", lambda *_: self._refilter())
        self._entry.connect("activate", lambda *_: self._activate_selected())

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self._entry.add_controller(key)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.connect("row-activated", lambda _l, row: self._choose(row))

        scrolled = Gtk.ScrolledWindow(child=self._list, vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._entry)
        box.append(scrolled)
        self.set_child(box)

        self.connect("map", lambda *_: self._entry.grab_focus())
        self._refilter()

    # -- building / filtering ------------------------------------------------

    def _refilter(self) -> None:
        self._list.remove_all()
        query = self._entry.get_text().strip().lower()
        shown = 0
        for entry in self._entries:
            text = (entry.search_text or f"{entry.title} {entry.subtitle}").lower()
            if query and query not in text:
                continue
            self._list.append(self._make_row(entry))
            shown += 1
            if shown >= _MAX_RESULTS:
                break
        first = self._list.get_row_at_index(0)
        if first is not None:
            self._list.select_row(first)

    def _make_row(self, entry: SwitchEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.payload = entry.payload

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(7)
        box.set_margin_bottom(7)
        box.set_margin_start(12)
        box.set_margin_end(12)

        top = Gtk.Box(spacing=8)
        if entry.state:
            dot = Gtk.Box(valign=Gtk.Align.CENTER)
            dot.add_css_class("status-dot")
            dot.add_css_class(entry.state)
            top.append(dot)
        name = Gtk.Label(label=entry.title, xalign=0.0)
        name.add_css_class("heading")
        name.set_ellipsize(_ELLIPSIZE_END)
        top.append(name)
        box.append(top)

        sub = Gtk.Label(label=entry.subtitle, xalign=0.0)
        sub.add_css_class("dim-label")
        sub.add_css_class("caption")
        sub.set_ellipsize(_ELLIPSIZE_END)
        box.append(sub)

        row.set_child(box)
        return row

    # -- navigation ----------------------------------------------------------

    def _on_key(self, _ctrl, keyval: int, _keycode: int, _state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Down:
            self._move(1)
            return True
        if keyval == Gdk.KEY_Up:
            self._move(-1)
            return True
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _move(self, delta: int) -> None:
        selected = self._list.get_selected_row()
        index = selected.get_index() if selected is not None else -1
        target = self._list.get_row_at_index(index + delta)
        if target is not None:
            self._list.select_row(target)
            target.grab_focus()  # scrolls it into view
            self._entry.grab_focus()  # keep typing in the entry

    # -- choosing ------------------------------------------------------------

    def _activate_selected(self) -> None:
        self._choose(self._list.get_selected_row())

    def _choose(self, row: Gtk.ListBoxRow | None) -> None:
        if row is not None and getattr(row, "payload", None) is not None:
            self._on_choose(row.payload)
            self.close()
