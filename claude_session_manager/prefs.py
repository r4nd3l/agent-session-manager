"""Preferences dialog: terminal font, scrollback, color scheme."""

from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, Pango  # noqa: E402

from .i18n import LANGUAGES, N_, _
from .state import AppState
from .themes import DEFAULT_THEME, THEME_NAMES, get_theme


def _hex_rgb(hex6: str) -> tuple[float, float, float]:
    return tuple(int(hex6[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _rounded_rect(cr, x, y, w, h, r):
    import math
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
    cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    cr.close_path()


def _draw_swatch(_area, cr, name: str) -> None:
    alloc = _area.get_allocation()
    width, height = alloc.width, alloc.height
    radius = 5
    theme = get_theme(name)
    if theme is None:
        cr.set_source_rgb(0.55, 0.55, 0.55)
        _rounded_rect(cr, 0, 0, width, height, radius)
        cr.fill()
        return
    r, g, b = _hex_rgb(theme["bg"])
    cr.set_source_rgb(r, g, b)
    _rounded_rect(cr, 0, 0, width, height, radius)
    cr.fill()
    r, g, b = _hex_rgb(theme["fg"])
    cr.set_source_rgb(r, g, b)
    _rounded_rect(cr, 6, 4, 10, height - 8, 2)
    cr.fill()
    sw, gap = 13, 3
    x = width - 6 * (sw + gap)
    for i in (1, 2, 3, 4, 5, 6):
        r, g, b = _hex_rgb(theme["palette"][i])
        cr.set_source_rgb(r, g, b)
        _rounded_rect(cr, x, 4, sw, height - 8, 2)
        cr.fill()
        x += sw + gap


def _theme_swatch(name: str) -> Gtk.DrawingArea:
    area = Gtk.DrawingArea()
    area.set_size_request(130, 22)
    area.set_valign(Gtk.Align.CENTER)
    area.connect("draw", _draw_swatch, name)
    return area


_SCHEMES = [
    ("system", N_("Follow system")),
    ("light", N_("Light")),
    ("dark", N_("Dark")),
]


def apply_color_scheme(value: str) -> None:
    settings = Gtk.Settings.get_default()
    if settings is None:
        return
    if value == "dark":
        settings.set_property("gtk-application-prefer-dark-theme", True)
    elif value == "light":
        settings.set_property("gtk-application-prefer-dark-theme", False)
    else:
        settings.set_property("gtk-application-prefer-dark-theme", False)


def _make_row(label_text: str) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    box.set_margin_start(12)
    box.set_margin_end(12)
    label = Gtk.Label(label=label_text, xalign=0.0)
    label.set_hexpand(True)
    box.pack_start(label, True, True, 0)
    return box


class PreferencesDialog(Gtk.Dialog):
    """on_change() is called after any setting is saved, so the window can
    push the new settings into open terminal tabs."""

    def __init__(self, state: AppState, on_change: Callable[[], None],
                 parent: Gtk.Window | None = None) -> None:
        super().__init__(title=_("Preferences"), transient_for=parent, modal=True)
        self.set_default_size(500, 550)
        self.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        self._state = state
        self._on_change = on_change

        content = self.get_content_area()
        content.set_spacing(4)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(8)
        vbox.set_margin_start(8)
        vbox.set_margin_end(8)

        # -- Terminal section --
        section_label = Gtk.Label(label=f"<b>{_('Terminal')}</b>", xalign=0.0, use_markup=True)
        section_label.set_margin_top(8)
        vbox.pack_start(section_label, False, False, 0)

        # Font
        font_box = _make_row(_("Font"))
        self._font_button = Gtk.FontButton()
        self._font_button.set_valign(Gtk.Align.CENTER)
        current_font = state.get_setting("font") or ""
        if current_font:
            self._font_button.set_font(current_font)
        self._font_button.connect("font-set", self._on_font_changed)
        font_box.pack_start(self._font_button, False, False, 0)

        reset_font = Gtk.Button.new_from_icon_name("edit-clear-symbolic", Gtk.IconSize.BUTTON)
        reset_font.get_style_context().add_class("flat")
        reset_font.set_tooltip_text(_("Reset to default font"))
        reset_font.connect("clicked", self._on_font_reset)
        font_box.pack_start(reset_font, False, False, 0)
        vbox.pack_start(font_box, False, False, 0)

        # Scrollback
        scroll_box = _make_row(_("Scrollback lines"))
        self._scroll_spin = Gtk.SpinButton.new_with_range(1_000, 1_000_000, 1_000)
        self._scroll_spin.set_value(int(state.get_setting("scrollback") or 10_000))
        self._scroll_spin.connect("value-changed", self._on_scrollback_changed)
        scroll_box.pack_start(self._scroll_spin, False, False, 0)
        vbox.pack_start(scroll_box, False, False, 0)

        # Color theme
        current_theme = state.get_setting("terminal_theme") or DEFAULT_THEME
        if current_theme not in THEME_NAMES:
            current_theme = DEFAULT_THEME
        theme_expander = Gtk.Expander(label=f"{_('Color theme')}: {current_theme}")
        self._theme_expander = theme_expander
        theme_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        radio_group = None
        for name in THEME_NAMES:
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_start(20)
            row_box.set_margin_top(2)
            row_box.set_margin_bottom(2)
            radio = Gtk.RadioButton.new_with_label_from_widget(radio_group, name)
            if radio_group is None:
                radio_group = radio
            radio.set_active(name == current_theme)
            radio.connect("toggled", self._on_theme_radio, name)
            row_box.pack_start(radio, False, False, 0)
            row_box.pack_end(_theme_swatch(name), False, False, 0)
            theme_box.pack_start(row_box, False, False, 0)
        theme_expander.add(theme_box)
        vbox.pack_start(theme_expander, False, False, 0)

        # -- Appearance section --
        section_label2 = Gtk.Label(label=f"<b>{_('Appearance')}</b>", xalign=0.0, use_markup=True)
        section_label2.set_margin_top(16)
        vbox.pack_start(section_label2, False, False, 0)

        scheme_box = _make_row(_("Color scheme"))
        self._scheme_combo = Gtk.ComboBoxText()
        for _k, label in _SCHEMES:
            self._scheme_combo.append_text(_(label))
        current_scheme = state.get_setting("color_scheme") or "system"
        self._scheme_combo.set_active(
            next((i for i, (k, _l) in enumerate(_SCHEMES) if k == current_scheme), 0)
        )
        self._scheme_combo.connect("changed", self._on_scheme_changed)
        scheme_box.pack_start(self._scheme_combo, False, False, 0)
        vbox.pack_start(scheme_box, False, False, 0)

        # -- Language section --
        current_lang = state.get_setting("language") or ""
        self._initial_lang = current_lang
        current_label = next(
            (label for code, label in LANGUAGES if code == current_lang), LANGUAGES[0][1]
        )

        section_label3 = Gtk.Label(label=f"<b>{_('Language')}</b>", xalign=0.0, use_markup=True)
        section_label3.set_margin_top(16)
        vbox.pack_start(section_label3, False, False, 0)

        restart_hint = Gtk.Label(label=_("Restart to apply"), xalign=0.0)
        restart_hint.get_style_context().add_class("dim-label")
        restart_hint.set_margin_start(12)
        vbox.pack_start(restart_hint, False, False, 0)

        self._restart_btn = Gtk.Button(label=_("Restart now"))
        self._restart_btn.get_style_context().add_class("suggested-action")
        self._restart_btn.set_no_show_all(True)
        self._restart_btn.set_visible(False)
        self._restart_btn.connect("clicked", self._on_restart)

        lang_expander = Gtk.Expander(label=f"{_('Language')}: {current_label}")
        self._lang_expander = lang_expander
        lang_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lang_radio_group = None
        for code, label in LANGUAGES:
            radio = Gtk.RadioButton.new_with_label_from_widget(lang_radio_group, label)
            if lang_radio_group is None:
                lang_radio_group = radio
            radio.set_active(code == current_lang)
            radio.connect("toggled", self._on_language_radio, code, label)
            radio.set_margin_start(20)
            lang_box.pack_start(radio, False, False, 0)
        lang_expander.add(lang_box)

        lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lang_row.pack_start(lang_expander, True, True, 0)
        lang_row.pack_start(self._restart_btn, False, False, 0)
        vbox.pack_start(lang_row, False, False, 0)

        # -- Notifications section --
        section_label4 = Gtk.Label(label=f"<b>{_('Notifications')}</b>", xalign=0.0, use_markup=True)
        section_label4.set_margin_top(16)
        vbox.pack_start(section_label4, False, False, 0)

        notify_box = _make_row(_("Notify when a session goes idle"))
        self._notify_switch = Gtk.Switch()
        self._notify_switch.set_valign(Gtk.Align.CENTER)
        self._notify_switch.set_active(bool(state.get_setting("notify_idle")))
        self._notify_switch.connect("notify::active", self._on_notify_changed)
        notify_box.pack_start(self._notify_switch, False, False, 0)
        vbox.pack_start(notify_box, False, False, 0)

        scrolled.add(vbox)
        content.pack_start(scrolled, True, True, 0)

    def present_prefs(self, parent: Gtk.Window | None = None) -> None:
        if parent is not None:
            self.set_transient_for(parent)
        self.show_all()
        self.run()
        self.destroy()

    def _on_font_changed(self, button: Gtk.FontButton) -> None:
        font_name = button.get_font()
        self._state.set_setting("font", font_name or "")
        self._on_change()

    def _on_font_reset(self, _button: Gtk.Button) -> None:
        self._font_button.set_font("Monospace 12")
        self._state.set_setting("font", "")
        self._on_change()

    def _on_scrollback_changed(self, spin: Gtk.SpinButton) -> None:
        self._state.set_setting("scrollback", int(spin.get_value()))
        self._on_change()

    def _on_theme_radio(self, radio: Gtk.RadioButton, name: str) -> None:
        if not radio.get_active():
            return
        self._state.set_setting("terminal_theme", name)
        self._theme_expander.set_label(f"{_('Color theme')}: {name}")
        self._on_change()

    def _on_scheme_changed(self, combo: Gtk.ComboBoxText) -> None:
        idx = combo.get_active()
        if idx < 0:
            return
        key = _SCHEMES[idx][0]
        self._state.set_setting("color_scheme", key)
        apply_color_scheme(key)
        self._on_change()

    def _on_notify_changed(self, switch: Gtk.Switch, _pspec) -> None:
        self._state.set_setting("notify_idle", switch.get_active())
        self._on_change()

    def _on_language_radio(self, radio: Gtk.RadioButton, code: str, label: str) -> None:
        if not radio.get_active():
            return
        self._state.set_setting("language", code)
        self._lang_expander.set_label(f"{_('Language')}: {label}")
        self._restart_btn.set_visible(code != self._initial_lang)
        self._on_change()

    def _on_restart(self, _button: Gtk.Button) -> None:
        subprocess.Popen(
            ["sh", "-c", f"sleep 1.5; exec {shlex.quote(sys.executable)} -m claude_session_manager"],
            start_new_session=True,
        )
        app = Gio.Application.get_default()
        if app is not None:
            app.quit()
