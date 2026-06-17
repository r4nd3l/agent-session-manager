"""Application entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .prefs import apply_color_scheme
from .state import AppState
from .store import SessionStore
from .window import MainWindow

# Bundled icons (e.g. tab-close-symbolic); found by name when installed.
_BUNDLED_ICONS = Path(__file__).resolve().parent.parent / "data" / "icons"

_CSS = b"""
/* ===== Claude Code Inspired Theme for Agent Session Manager ===== */

@define-color cc_accent #D97757;
@define-color cc_accent2 #bb9af7;

/* == Global widget styles ======================================== */

/* -- Headerbars: subtle accent bottom border --------------------- */
headerbar {
  padding: 3px 8px;
  min-height: 38px;
  border-bottom: 1px solid alpha(@cc_accent, 0.12);
}
headerbar button { border-radius: 6px; }
headerbar button:hover { background-color: alpha(@cc_accent, 0.10); }

/* -- Entries & search entries: rounded, tighter ------------------- */
entry, searchentry {
  border-radius: 8px;
  min-height: 30px;
  padding: 0 10px;
}
entry:focus, searchentry:focus {
  border-color: alpha(@cc_accent, 0.5);
  box-shadow: 0 0 0 1px alpha(@cc_accent, 0.2);
}

/* -- Scrollbars: thin, modern ------------------------------------ */
scrollbar { background: transparent; }
scrollbar trough { background: transparent; min-width: 8px; min-height: 8px; }
scrollbar slider {
  min-width: 4px;
  min-height: 20px;
  border-radius: 100px;
  background-color: alpha(currentColor, 0.12);
}
scrollbar slider:hover { background-color: alpha(currentColor, 0.25); }
scrollbar slider:active { background-color: alpha(@cc_accent, 0.45); }

/* -- Pane divider ------------------------------------------------ */
paned > separator {
  min-width: 1px;
  background-color: alpha(@cc_accent, 0.12);
}

/* -- Flat buttons: accent hover ---------------------------------- */
button.flat:hover { background-color: alpha(@cc_accent, 0.10); }
button.flat:active { background-color: alpha(@cc_accent, 0.18); }

/* -- Suggested action button: Claude orange ---------------------- */
button.suggested-action {
  background-color: @cc_accent;
  color: white;
  border: none;
}
button.suggested-action:hover {
  background-color: shade(@cc_accent, 1.1);
}

/* -- Destructive button: red tint -------------------------------- */
button.destructive-action {
  background-color: #f7768e;
  color: white;
  border: none;
}

/* -- Switch: accent when on -------------------------------------- */
switch:checked { background-color: @cc_accent; }
switch:checked slider { background-color: white; }

/* -- Popovers / menus: rounded, accent selection ----------------- */
popover { border-radius: 10px; }
popover modelbutton:hover { background-color: alpha(@cc_accent, 0.10); }

/* -- Dialogs ----------------------------------------------------- */
dialog .dialog-action-area button {
  border-radius: 6px;
  min-height: 32px;
  padding: 4px 16px;
}

/* -- Lists: clean hover / selection ------------------------------ */
list row:hover { background-color: alpha(@cc_accent, 0.05); }
list row:selected { background-color: alpha(@cc_accent, 0.10); }

/* == Sidebar-specific ============================================ */

.cc-sidebar {
  border-right: 1px solid alpha(@cc_accent, 0.08);
}

/* -- Sidebar brand header ---------------------------------------- */
.cc-brand-box {
  padding: 12px 14px 10px 14px;
  border-bottom: 1px solid alpha(@cc_accent, 0.10);
}
.cc-brand-title { font-weight: bold; font-size: 1.05em; }
.cc-brand-sub   { font-size: 0.78em; opacity: 0.4; }

/* == Session list elements ======================================= */

/* -- Status dots ------------------------------------------------- */
.status-dot {
  min-width: 9px;
  min-height: 9px;
  border-radius: 100%;
  background-color: alpha(currentColor, 0.10);
}
.status-dot.open {
  background-color: #2ec27e;
  box-shadow: 0 0 6px alpha(#2ec27e, 0.4);
}
.status-dot.attention {
  background-color: #7aa2f7;
  box-shadow: 0 0 6px alpha(#7aa2f7, 0.4);
}

/* -- Group headers ----------------------------------------------- */
.group-header { padding: 14px 12px 6px 12px; }

/* -- Session-row state badges ------------------------------------ */
.waiting-badge { color: #e0af68; }
.interrupted-badge { color: #f7768e; }

/* -- Count badge ------------------------------------------------- */
.count-badge {
  background-color: alpha(@cc_accent, 0.12);
  color: @cc_accent;
  border-radius: 100px;
  padding: 1px 8px;
  font-size: 0.78em;
  font-weight: bold;
}

/* -- Session card rows ------------------------------------------- */
row.session-child {
  margin-left: 14px;
  margin-right: 6px;
  margin-top: 1px;
  margin-bottom: 1px;
  background-color: alpha(currentColor, 0.03);
  border-left: 2px solid alpha(@cc_accent, 0.12);
  border-radius: 0 8px 8px 0;
  transition: 150ms ease;
}
row.session-child:hover {
  background-color: alpha(@cc_accent, 0.08);
  border-left-color: @cc_accent;
}
row.session-child:selected,
row.session-child:active {
  background-color: alpha(@cc_accent, 0.13);
  border-left-color: @cc_accent;
}

/* == Notebook tabs =============================================== */

notebook header { border-bottom: 1px solid alpha(@cc_accent, 0.08); }

notebook tab {
  padding: 6px 12px;
  border-radius: 6px 6px 0 0;
  border-bottom: 2px solid transparent;
  transition: 150ms ease;
}
notebook tab:checked {
  background-color: alpha(@cc_accent, 0.12);
  border-bottom-color: @cc_accent;
}
notebook tab:checked label { font-weight: bold; opacity: 1.0; }
notebook tab label { opacity: 0.40; }
notebook tab:hover {
  background-color: alpha(@cc_accent, 0.06);
}
notebook tab:hover label { opacity: 0.75; }

/* -- Tab close button -------------------------------------------- */
notebook tab button {
  min-width: 18px;
  min-height: 18px;
  padding: 0;
  border-radius: 100px;
  opacity: 0.4;
}
notebook tab button:hover {
  opacity: 1.0;
  background-color: alpha(#f7768e, 0.2);
}

/* == Typography ================================================== */

.heading { font-weight: bold; }
.caption { font-size: 0.85em; }

/* == Footer ====================================================== */

.sidebar-footer {
  font-size: 0.80em;
  padding: 8px 14px;
  border-top: 1px solid alpha(currentColor, 0.06);
}

/* == Empty-state placeholder ===================================== */

.cc-placeholder-icon { opacity: 0.15; }
.cc-placeholder-title {
  font-size: 1.35em;
  font-weight: bold;
  opacity: 0.50;
}
.cc-placeholder-desc { opacity: 0.30; font-size: 0.95em; }
.cc-placeholder-shortcut {
  font-size: 0.82em;
  opacity: 0.25;
  font-family: monospace;
}
.cc-kbd {
  background-color: alpha(currentColor, 0.08);
  border: 1px solid alpha(currentColor, 0.10);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.80em;
  font-family: monospace;
  font-weight: bold;
}
.cc-logo-art {
  font-family: monospace;
  font-size: 0.7em;
  opacity: 0.12;
}

/* == Quick-switcher ============================================== */

.switcher-entry {
  font-size: 1.05em;
  min-height: 36px;
}
.switcher-row {
  border-radius: 8px;
  margin: 1px 8px;
}
.switcher-row:selected {
  background-color: alpha(@cc_accent, 0.12);
}

/* == Action bar =================================================== */

actionbar {
  border-top: 1px solid alpha(@cc_accent, 0.12);
  padding: 2px 4px;
}

/* == Terminal panel ================================================ */

.cc-terminal-frame {
  /* bg set programmatically to match the active VTE theme */
}

/* -- Terminal info bar (top) -------------------------------------- */
.cc-term-infobar {
  border-bottom: 1px solid alpha(@cc_accent, 0.10);
  padding: 4px 6px;
}
.cc-infobar-provider {
  font-weight: bold;
  font-size: 0.88em;
}
.cc-infobar-project {
  font-size: 0.88em;
  opacity: 0.7;
}
.cc-infobar-sid {
  font-family: monospace;
  font-size: 0.78em;
  opacity: 0.35;
}
.cc-fork-badge {
  background-color: alpha(@cc_accent2, 0.15);
  color: @cc_accent2;
  border-radius: 4px;
  padding: 0 6px;
  font-size: 0.7em;
  font-weight: bold;
}

/* -- Terminal status bar (bottom) --------------------------------- */
.cc-term-statusbar {
  border-top: 1px solid alpha(@cc_accent, 0.08);
  padding: 3px 6px;
}
.cc-statusbar-text {
  font-size: 0.78em;
  opacity: 0.45;
}

/* -- Terminal search bar ------------------------------------------ */
.cc-search-bar {
  background-color: alpha(@cc_accent, 0.04);
  border-bottom: 1px solid alpha(@cc_accent, 0.10);
  padding: 4px 8px;
}
.cc-search-bar entry {
  border-radius: 6px;
  min-height: 28px;
}
.cc-search-btn {
  min-width: 28px;
  min-height: 28px;
  padding: 0;
  border-radius: 100px;
}
.cc-search-btn:hover {
  background-color: alpha(@cc_accent, 0.15);
}

/* == Accent utility classes ======================================= */

.cc-accent-btn:hover { color: @cc_accent; }
.cc-accent-icon { color: @cc_accent; opacity: 0.7; }
"""


APP_ID = "io.github.r4nd3l.AgentSessionManager"


class App(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=os.environ.get("CSM_APP_ID") or APP_ID)

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        screen = Gdk.Screen.get_default()
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        if _BUNDLED_ICONS.is_dir():
            Gtk.IconTheme.get_default().append_search_path(str(_BUNDLED_ICONS))

        self.state = AppState()
        apply_color_scheme(self.state.get_setting("color_scheme"))
        self.store = SessionStore(self.state)
        self.store.start()

        focus = Gio.SimpleAction.new("focus-session", GLib.VariantType("s"))
        focus.connect("activate", self._on_focus_session)
        self.add_action(focus)

        new_window = Gio.SimpleAction.new("new-window", None)
        new_window.connect("activate", lambda *_: self._new_window())
        self.add_action(new_window)
        self.set_accels_for_action("app.new-window", ["<Control><Shift>n"])

    def _new_window(self) -> MainWindow:
        window = MainWindow(application=self, state=self.state, store=self.store)
        window.show_all()
        return window

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
            window = self._new_window()
        window.present()


def main() -> int:
    from . import i18n
    from .state import AppState

    i18n.init(AppState().get_setting("language"))
    app = App()
    return app.run(sys.argv)
