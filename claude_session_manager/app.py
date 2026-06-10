"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .window import MainWindow

# Bundled icons (e.g. tab-close-symbolic); found by name when installed.
_BUNDLED_ICONS = Path(__file__).resolve().parent.parent / "data" / "icons"

_CSS = b"""
.status-dot {
  min-width: 8px;
  min-height: 8px;
  border-radius: 100%;
  background-color: alpha(currentColor, 0.25);
}
.status-dot.open { background-color: #2ec27e; }
.status-dot.attention { background-color: #3584e4; }

.group-header { padding: 10px 10px 4px 10px; }

/* make the active tab clearly stand out from inactive ones */
tabbar tab:checked {
  background-color: alpha(#D97757, 0.22);
  box-shadow: inset 0 -3px 0 #D97757;
}
tabbar tab:checked label { font-weight: bold; }
tabbar tab:not(:checked) label { opacity: 0.6; }

.count-badge {
  background-color: alpha(currentColor, 0.1);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 0.8em;
}

/* children connect to their group via a left guide line, on a faint card */
row.session-child {
  margin-left: 20px;
  margin-right: 16px;
  background-color: alpha(currentColor, 0.06);
  border-left: 2px solid alpha(currentColor, 0.15);
  border-radius: 0 8px 8px 0;
}
row.session-child:hover {
  background-color: alpha(currentColor, 0.1);
  border-left-color: alpha(currentColor, 0.3);
}
"""


class App(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="eu.zengo.ClaudeSessionManager")

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        display = Gdk.Display.get_default()
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        if _BUNDLED_ICONS.is_dir():  # running from source; installed icons live in the system theme
            Gtk.IconTheme.get_for_display(display).add_search_path(str(_BUNDLED_ICONS))

        focus = Gio.SimpleAction.new("focus-session", GLib.VariantType("s"))
        focus.connect("activate", self._on_focus_session)
        self.add_action(focus)

    def _on_focus_session(self, _action, param: GLib.Variant) -> None:
        window = self.get_active_window()
        if window is None:
            return
        window.present()
        session_id = param.get_string()
        if session_id and hasattr(window, "focus_session"):
            window.focus_session(session_id)

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is None:
            window = MainWindow(application=self)
        window.present()


def main() -> int:
    app = App()
    return app.run(sys.argv)
