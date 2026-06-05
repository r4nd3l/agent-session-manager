"""Application entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from .window import MainWindow

_CSS = b"""
.status-dot {
  min-width: 8px;
  min-height: 8px;
  border-radius: 100%;
  background-color: alpha(currentColor, 0.25);
}
.status-dot.open { background-color: #2ec27e; }
.status-dot.attention { background-color: #3584e4; }
.group-header { padding: 8px 12px 2px 12px; }
"""


class App(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="eu.zengo.ClaudeSessionManager")

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is None:
            window = MainWindow(application=self)
        window.present()


def main() -> int:
    app = App()
    return app.run(sys.argv)
