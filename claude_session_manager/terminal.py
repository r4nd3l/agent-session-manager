"""A tab hosting a VTE terminal running the user's shell with `claude` inside."""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, GLib, GObject, Gtk, Pango, Vte  # noqa: E402

from . import themes  # noqa: E402

# PCRE2 flags for the find bar: multiline, case-insensitive.
_PCRE2_CASELESS = 0x00000008
_PCRE2_MULTILINE = 0x00000400
_SEARCH_FLAGS = _PCRE2_CASELESS | _PCRE2_MULTILINE


class TerminalTab(Gtk.Box):
    """Embeds Vte.Terminal (with a find bar) and spawns the claude CLI into it."""

    __gsignals__ = {
        # Emitted when the claude process exits (int = exit status).
        "process-exited": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(
        self,
        cwd: str | None,
        session_id: str | None = None,
        fork: bool = False,
        settings: dict | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.session_id = session_id
        self.fork = fork
        self._child_pid: int | None = None

        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10_000)
        self.terminal.set_scroll_on_output(False)
        self.terminal.set_scroll_on_keystroke(True)
        self.terminal.set_mouse_autohide(True)
        self.terminal.connect("child-exited", self._on_child_exited)

        self._search_bar = self._build_search_bar()
        self.append(self._search_bar)

        scrolled = Gtk.ScrolledWindow(child=self.terminal, vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.append(scrolled)

        # Ctrl+Shift+C / Ctrl+Shift+V / Ctrl+Shift+G, terminal-style
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.terminal.add_controller(keys)

        if settings:
            self.apply_settings(settings)
        self._spawn(cwd, session_id)

    # -- spawning ----------------------------------------------------------

    def _spawn(self, cwd: str | None, session_id: str | None) -> None:
        if cwd is None or not Path(cwd).is_dir():
            if cwd is not None:
                self.feed_message(f"warning: project dir {cwd} no longer exists, starting in HOME")
            cwd = str(Path.home())

        # Run the user's interactive shell and type the claude command into it,
        # so aliases/env apply and the tab drops to a prompt when claude exits.
        # The tab closes when the *shell* exits.
        self._initial_command: str | None = None
        claude = shutil.which("claude")
        if claude is None:
            self.feed_message("warning: `claude` not found in PATH — starting a plain shell")
        else:
            command = shlex.quote(claude)
            if session_id is not None:
                command += f" --resume {shlex.quote(session_id)}"
                if self.fork:
                    command += " --fork-session"
            self._initial_command = command

        shell = os.environ.get("SHELL") or "/bin/bash"
        argv = [shell]

        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            cwd,
            argv,
            None,  # envv: inherit
            GLib.SpawnFlags.DEFAULT,
            None,  # child_setup
            None,  # child_setup_data
            -1,  # timeout
            None,  # cancellable
            self._on_spawned,
        )

    def _on_spawned(self, terminal: Vte.Terminal, pid: int, error: GLib.Error | None) -> None:
        if error is not None:
            self.feed_message(f"failed to start shell: {error.message}")
            return
        self._child_pid = pid
        if self._initial_command:
            terminal.feed_child(f"{self._initial_command}\n".encode())

    def _on_child_exited(self, terminal: Vte.Terminal, status: int) -> None:
        self.emit("process-exited", status)

    # -- search bar --------------------------------------------------------

    def _build_search_bar(self) -> Gtk.SearchBar:
        bar = Gtk.SearchBar()
        self._search_entry = Gtk.SearchEntry(hexpand=True, placeholder_text="Find in terminal…")
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", lambda *_: self._search_step(forward=False))
        self._search_entry.connect("next-match", lambda *_: self._search_step(forward=True))
        self._search_entry.connect("previous-match", lambda *_: self._search_step(forward=False))
        self._search_entry.connect("stop-search", lambda *_: self.hide_search())

        prev_btn = Gtk.Button(icon_name="go-up-symbolic", tooltip_text="Previous match")
        prev_btn.connect("clicked", lambda *_: self._search_step(forward=False))
        next_btn = Gtk.Button(icon_name="go-down-symbolic", tooltip_text="Next match")
        next_btn.connect("clicked", lambda *_: self._search_step(forward=True))

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(self._search_entry)
        box.append(prev_btn)
        box.append(next_btn)
        bar.set_child(box)
        bar.connect_entry(self._search_entry)
        bar.set_show_close_button(True)
        bar.connect("notify::search-mode-enabled", self._on_search_mode_changed)
        self.terminal.search_set_wrap_around(True)
        return bar

    def _on_search_mode_changed(self, bar: Gtk.SearchBar, _pspec) -> None:
        if not bar.get_search_mode():  # cleared via the close button or Escape
            self.terminal.search_set_regex(None, 0)
            self.grab_terminal_focus()

    def toggle_search(self) -> None:
        if self._search_bar.get_search_mode():
            self.hide_search()
        else:
            self._search_bar.set_search_mode(True)
            self._search_entry.grab_focus()

    def hide_search(self) -> None:
        # _on_search_mode_changed clears the regex and refocuses the terminal.
        self._search_bar.set_search_mode(False)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text()
        if not query:
            self.terminal.search_set_regex(None, 0)
            return
        pattern = GLib.Regex.escape_string(query, -1)
        try:
            regex = Vte.Regex.new_for_search(pattern, len(pattern.encode()), _SEARCH_FLAGS)
        except GLib.Error:
            return
        self.terminal.search_set_regex(regex, 0)
        self._search_step(forward=False)  # nearest match above the prompt

    def _search_step(self, forward: bool) -> None:
        if forward:
            self.terminal.search_find_next()
        else:
            self.terminal.search_find_previous()

    # -- graceful close ----------------------------------------------------

    def feed_child_text(self, text: str) -> None:
        self.terminal.feed_child(text.encode())

    # -- helpers -----------------------------------------------------------

    def has_running_command(self) -> bool:
        """True when something other than the shell (e.g. claude) owns the
        terminal's foreground — the cue terminal emulators use for
        close-confirmation."""
        if self._child_pid is None:
            return False
        pty = self.terminal.get_pty()
        if pty is None:
            return False
        try:
            foreground = os.tcgetpgrp(pty.get_fd())
            return foreground not in (-1, os.getpgid(self._child_pid))
        except OSError:
            return False

    def apply_settings(self, settings: dict) -> None:
        font = settings.get("font") or ""
        self.terminal.set_font(Pango.FontDescription.from_string(font) if font else None)
        try:
            self.terminal.set_scrollback_lines(int(settings.get("scrollback") or 10_000))
        except (TypeError, ValueError):
            pass
        themes.apply_terminal_theme(self.terminal, settings.get("terminal_theme"))

    def feed_message(self, text: str) -> None:
        self.terminal.feed(f"\r\n\x1b[1;33m[session manager]\x1b[0m {text}\r\n".encode())

    def grab_terminal_focus(self) -> None:
        self.terminal.grab_focus()

    def _on_key_pressed(self, _ctrl, keyval: int, _keycode: int, state: Gdk.ModifierType) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)

        # Shift+Enter → newline. Terminals send the same byte for Enter and
        # Shift+Enter, so we emit Meta+Enter (ESC + CR), which Claude Code
        # interprets as "insert a line break" rather than "submit".
        if shift and not ctrl and keyval in (
            Gdk.KEY_Return,
            Gdk.KEY_KP_Enter,
            Gdk.KEY_ISO_Enter,
        ):
            self.terminal.feed_child(b"\x1b\r")
            return True

        if ctrl and shift:
            if keyval == Gdk.KEY_C:
                self.terminal.copy_clipboard_format(Vte.Format.TEXT)
                return True
            if keyval == Gdk.KEY_V:
                self.terminal.paste_clipboard()
                return True
            if keyval == Gdk.KEY_G:
                self.toggle_search()
                return True
        return False
