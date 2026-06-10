"""Preferences dialog: terminal font, scrollback, color scheme."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Pango  # noqa: E402

from .state import AppState

_SCHEMES = [
    ("system", "Follow system", Adw.ColorScheme.DEFAULT),
    ("light", "Light", Adw.ColorScheme.FORCE_LIGHT),
    ("dark", "Dark", Adw.ColorScheme.FORCE_DARK),
]


def apply_color_scheme(value: str) -> None:
    for key, _label, scheme in _SCHEMES:
        if key == value:
            Adw.StyleManager.get_default().set_color_scheme(scheme)
            return


class PreferencesDialog(Adw.PreferencesDialog):
    """on_change() is called after any setting is saved, so the window can
    push the new settings into open terminal tabs."""

    def __init__(self, state: AppState, on_change: Callable[[], None]) -> None:
        super().__init__(title="Preferences")
        self._state = state
        self._on_change = on_change

        page = Adw.PreferencesPage(title="General", icon_name="preferences-system-symbolic")

        terminal_group = Adw.PreferencesGroup(title="Terminal")

        font_row = Adw.ActionRow(title="Font", subtitle="Applies to all terminal tabs")
        self._font_button = Gtk.FontDialogButton(dialog=Gtk.FontDialog(), valign=Gtk.Align.CENTER)
        current_font = state.get_setting("font") or ""
        if current_font:
            self._font_button.set_font_desc(Pango.FontDescription.from_string(current_font))
        self._font_button.connect("notify::font-desc", self._on_font_changed)
        font_row.add_suffix(self._font_button)

        reset_font = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER)
        reset_font.add_css_class("flat")
        reset_font.set_tooltip_text("Reset to default font")
        reset_font.connect("clicked", self._on_font_reset)
        font_row.add_suffix(reset_font)
        terminal_group.add(font_row)

        scroll_row = Adw.SpinRow.new_with_range(1_000, 1_000_000, 1_000)
        scroll_row.set_title("Scrollback lines")
        scroll_row.set_value(int(state.get_setting("scrollback") or 10_000))
        scroll_row.connect("notify::value", self._on_scrollback_changed)
        terminal_group.add(scroll_row)
        page.add(terminal_group)

        appearance_group = Adw.PreferencesGroup(title="Appearance")
        scheme_row = Adw.ComboRow(title="Color scheme")
        scheme_row.set_model(Gtk.StringList.new([label for _k, label, _s in _SCHEMES]))
        current_scheme = state.get_setting("color_scheme") or "system"
        scheme_row.set_selected(
            next((i for i, (k, _l, _s) in enumerate(_SCHEMES) if k == current_scheme), 0)
        )
        scheme_row.connect("notify::selected", self._on_scheme_changed)
        appearance_group.add(scheme_row)
        page.add(appearance_group)

        notif_group = Adw.PreferencesGroup(title="Notifications")
        self._notify_row = Adw.SwitchRow(
            title="Notify when a session goes idle",
            subtitle="Desktop notification when a background tab stops producing output",
        )
        self._notify_row.set_active(bool(state.get_setting("notify_idle")))
        self._notify_row.connect("notify::active", self._on_notify_changed)
        notif_group.add(self._notify_row)
        page.add(notif_group)

        self.add(page)

    def _on_font_changed(self, button: Gtk.FontDialogButton, _pspec) -> None:
        desc = button.get_font_desc()
        self._state.set_setting("font", desc.to_string() if desc else "")
        self._on_change()

    def _on_font_reset(self, _button: Gtk.Button) -> None:
        self._font_button.set_font_desc(None)
        self._state.set_setting("font", "")
        self._on_change()

    def _on_scrollback_changed(self, row: Adw.SpinRow, _pspec) -> None:
        self._state.set_setting("scrollback", int(row.get_value()))
        self._on_change()

    def _on_scheme_changed(self, row: Adw.ComboRow, _pspec) -> None:
        key = _SCHEMES[row.get_selected()][0]
        self._state.set_setting("color_scheme", key)
        apply_color_scheme(key)
        self._on_change()

    def _on_notify_changed(self, row: Adw.SwitchRow, _pspec) -> None:
        self._state.set_setting("notify_idle", row.get_active())
        self._on_change()
