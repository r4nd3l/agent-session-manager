"""A tab hosting a VTE terminal running the user's shell with an agent CLI inside."""

from __future__ import annotations

import os
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, GLib, GObject, Gtk, Pango, Vte  # noqa: E402

import re as _re  # noqa: E402
from . import themes  # noqa: E402
from .i18n import _  # noqa: E402
from .providers import Provider, get_provider  # noqa: E402

_SEARCH_FLAGS = GLib.RegexCompileFlags.CASELESS | GLib.RegexCompileFlags.MULTILINE

_PREFERRED_FONTS = [
    "JetBrains Mono",
    "Cascadia Code",
    "Fira Code",
    "Source Code Pro",
    "Ubuntu Mono",
    "DejaVu Sans Mono",
]

_PAD_LEFT = 12
_PAD_RIGHT = 6
_PAD_TOP = 4
_PAD_BOTTOM = 2

# ANSI 256/truecolor helpers
_O = "\x1b[38;2;217;119;87m"  # Claude orange
_D = "\x1b[38;2;86;95;137m"   # dim
_W = "\x1b[38;2;192;202;245m" # white text
_B = "\x1b[1m"                # bold
_R = "\x1b[0m"                # reset


def _pick_font() -> str | None:
    try:
        import subprocess
        out = subprocess.check_output(
            ["fc-list", ":spacing=mono", "family"],
            text=True, timeout=2,
        )
        installed = {f.strip() for line in out.splitlines() for f in line.split(",")}
    except Exception:
        return None
    for font in _PREFERRED_FONTS:
        if font in installed:
            return font
    return None


_CACHED_FONT: str | None | bool = False


def _default_font() -> str:
    global _CACHED_FONT
    if _CACHED_FONT is False:
        _CACHED_FONT = _pick_font()
    return f"{_CACHED_FONT} 13" if _CACHED_FONT else "Monospace 13"


def _make_banner(provider_name: str, session_id: str | None, cwd: str | None,
                 fork: bool) -> str:
    """Build a colorful ANSI welcome banner fed into the terminal on spawn."""
    sid_short = session_id[:12] + "..." if session_id and len(session_id) > 15 else (session_id or "new")
    proj = Path(cwd).name if cwd else "~"
    mode = "fork" if fork else ("resume" if session_id else "new session")

    w = 52
    top = f"{_O}{'~' * w}{_R}"
    bot = f"{_O}{'~' * w}{_R}"
    blank = f"{_O}~{_R}{' ' * (w - 2)}{_O}~{_R}"

    lines = [
        "",
        top,
        blank,
        f"{_O}~{_R}  {_O}{_B}Agent Session Manager{_R}{' ' * (w - 25)}{_O}~{_R}",
        blank,
        f"{_O}~{_R}  {_D}Provider{_R}  {_W}{provider_name}{_R}{' ' * (w - 14 - len(provider_name))}{_O}~{_R}",
        f"{_O}~{_R}  {_D}Session {_R}  {_W}{sid_short}{_R}{' ' * (w - 14 - len(sid_short))}{_O}~{_R}",
        f"{_O}~{_R}  {_D}Project {_R}  {_W}{proj}{_R}{' ' * (w - 14 - len(proj))}{_O}~{_R}",
        f"{_O}~{_R}  {_D}Mode    {_R}  {_W}{mode}{_R}{' ' * (w - 14 - len(mode))}{_O}~{_R}",
        blank,
        bot,
        "",
    ]
    return "\r\n".join(lines)


class TerminalTab(Gtk.Box):
    """Embeds Vte.Terminal (with a find bar) and spawns an agent CLI into it."""

    __gsignals__ = {
        "process-exited": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(
        self,
        cwd: str | None,
        session_id: str | None = None,
        fork: bool = False,
        settings: dict | None = None,
        provider: Provider | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.session_id = session_id
        self.fork = fork
        self.provider = provider or get_provider("claude")
        self._child_pid: int | None = None
        self._cwd = cwd

        # -- terminal widget -----------------------------------------------
        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10_000)
        self.terminal.set_scroll_on_output(False)
        self.terminal.set_scroll_on_keystroke(True)
        self.terminal.set_mouse_autohide(True)
        self.terminal.set_cursor_shape(Vte.CursorShape.IBEAM)
        self.terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        self.terminal.set_bold_is_bright(False)
        self.terminal.set_cell_height_scale(1.2)
        self.terminal.set_cell_width_scale(1.0)
        self.terminal.set_font(Pango.FontDescription.from_string(_default_font()))
        self.terminal.connect("child-exited", self._on_child_exited)

        # -- top info bar --------------------------------------------------
        self._info_bar = self._build_info_bar(cwd, session_id)
        self.pack_start(self._info_bar, False, False, 0)

        # -- search bar ----------------------------------------------------
        self._search_bar = self._build_search_bar()
        self.pack_start(self._search_bar, False, False, 0)

        # -- padded frame around terminal ----------------------------------
        self._frame = Gtk.EventBox()
        self._frame.get_style_context().add_class("cc-terminal-frame")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_margin_start(_PAD_LEFT)
        scrolled.set_margin_end(_PAD_RIGHT)
        scrolled.set_margin_top(_PAD_TOP)
        scrolled.set_margin_bottom(_PAD_BOTTOM)
        scrolled.add(self.terminal)

        frame_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame_inner.pack_start(scrolled, True, True, 0)
        self._frame.add(frame_inner)
        self.pack_start(self._frame, True, True, 0)

        # -- bottom status bar ---------------------------------------------
        self._status_bar = self._build_status_bar(cwd, session_id)
        self.pack_start(self._status_bar, False, False, 0)

        # -- keyboard shortcuts -------------------------------------------
        self.terminal.connect("key-press-event", self._on_key_pressed)

        if settings:
            self.apply_settings(settings)
        self._spawn(cwd, session_id)

    # -- info bar (top) ----------------------------------------------------

    def _build_info_bar(self, cwd: str | None, session_id: str | None) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.get_style_context().add_class("cc-term-infobar")
        bar.set_margin_start(10)
        bar.set_margin_end(10)
        bar.set_margin_top(5)
        bar.set_margin_bottom(3)

        icon = Gtk.Image.new_from_icon_name(
            self.provider.icon_name if hasattr(self.provider, 'icon_name') else "utilities-terminal-symbolic",
            Gtk.IconSize.MENU,
        )
        icon.get_style_context().add_class("cc-accent-icon")
        bar.pack_start(icon, False, False, 0)

        provider_lbl = Gtk.Label(label=self.provider.name)
        provider_lbl.get_style_context().add_class("cc-infobar-provider")
        bar.pack_start(provider_lbl, False, False, 0)

        sep = Gtk.Label(label="/")
        sep.get_style_context().add_class("dim-label")
        bar.pack_start(sep, False, False, 0)

        proj = Path(cwd).name if cwd else "~"
        proj_lbl = Gtk.Label(label=proj)
        proj_lbl.get_style_context().add_class("cc-infobar-project")
        proj_lbl.set_ellipsize(3)
        bar.pack_start(proj_lbl, False, False, 0)

        if self.fork:
            fork_badge = Gtk.Label(label="FORK")
            fork_badge.get_style_context().add_class("cc-fork-badge")
            bar.pack_start(fork_badge, False, False, 0)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.pack_start(spacer, True, True, 0)

        if session_id:
            sid_short = session_id[:8]
            sid_lbl = Gtk.Label(label=sid_short)
            sid_lbl.get_style_context().add_class("cc-infobar-sid")
            sid_lbl.set_tooltip_text(session_id)
            bar.pack_end(sid_lbl, False, False, 0)

        return bar

    # -- status bar (bottom) -----------------------------------------------

    def _build_status_bar(self, cwd: str | None, session_id: str | None) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bar.get_style_context().add_class("cc-term-statusbar")
        bar.set_margin_start(10)
        bar.set_margin_end(10)
        bar.set_margin_top(2)
        bar.set_margin_bottom(3)

        self._status_dot = Gtk.Box()
        self._status_dot.set_valign(Gtk.Align.CENTER)
        self._status_dot.get_style_context().add_class("status-dot")
        self._status_dot.get_style_context().add_class("open")
        self._status_dot.set_size_request(7, 7)
        bar.pack_start(self._status_dot, False, False, 0)

        self._status_label = Gtk.Label(label=_("Running"))
        self._status_label.get_style_context().add_class("cc-statusbar-text")
        bar.pack_start(self._status_label, False, False, 0)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.pack_start(spacer, True, True, 0)

        if cwd:
            dir_icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.MENU)
            dir_icon.get_style_context().add_class("dim-label")
            bar.pack_end(dir_icon, False, False, 0)
            dir_lbl = Gtk.Label(label=cwd)
            dir_lbl.get_style_context().add_class("cc-statusbar-text")
            dir_lbl.set_ellipsize(3)
            dir_lbl.set_max_width_chars(50)
            dir_lbl.set_tooltip_text(cwd)
            bar.pack_end(dir_lbl, False, False, 0)

        return bar

    # -- spawning ----------------------------------------------------------

    def _spawn(self, cwd: str | None, session_id: str | None) -> None:
        if cwd is None or not Path(cwd).is_dir():
            if cwd is not None:
                self.feed_message(
                    _("warning: project dir {cwd} no longer exists, starting in HOME").format(cwd=cwd)
                )
            cwd = str(Path.home())

        self._initial_command: str | None = None
        if session_id is not None:
            command = self.provider.resume_command(session_id, fork=self.fork)
        else:
            command = self.provider.new_command()
        if command is None:
            self.feed_message(
                _("warning: `{cli}` not found in PATH").format(cli=self.provider.cli)
            )
        else:
            self._initial_command = command

        shell = os.environ.get("SHELL") or "/bin/bash"
        argv = [shell]

        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            cwd,
            argv,
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            self._on_spawned,
        )

    def _on_spawned(
        self,
        terminal: Vte.Terminal,
        pid: int,
        error: GLib.Error | None,
        _user_data=None,
    ) -> None:
        if error is not None:
            self.feed_message(_("failed to start shell: {msg}").format(msg=error.message))
            return
        self._child_pid = pid
        banner = _make_banner(
            self.provider.name, self.session_id, self._cwd, self.fork,
        )
        terminal.feed(banner.encode())
        if self._initial_command:
            terminal.feed_child(f"{self._initial_command}\n".encode())

    def _on_child_exited(self, terminal: Vte.Terminal, status: int) -> None:
        self._status_label.set_label(_("Exited"))
        ctx = self._status_dot.get_style_context()
        ctx.remove_class("open")
        self.emit("process-exited", status)

    # -- search bar --------------------------------------------------------

    def _build_search_bar(self) -> Gtk.SearchBar:
        bar = Gtk.SearchBar()
        bar.get_style_context().add_class("cc-search-bar")
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(True)
        self._search_entry.set_placeholder_text(_("Find in terminal..."))
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", lambda *_: self._search_step(forward=False))
        self._search_entry.connect("next-match", lambda *_: self._search_step(forward=True))
        self._search_entry.connect("previous-match", lambda *_: self._search_step(forward=False))
        self._search_entry.connect("stop-search", lambda *_: self.hide_search())

        prev_btn = Gtk.Button.new_from_icon_name("go-up-symbolic", Gtk.IconSize.MENU)
        prev_btn.get_style_context().add_class("flat")
        prev_btn.get_style_context().add_class("cc-search-btn")
        prev_btn.set_tooltip_text(_("Previous match"))
        prev_btn.connect("clicked", lambda *_: self._search_step(forward=False))
        next_btn = Gtk.Button.new_from_icon_name("go-down-symbolic", Gtk.IconSize.MENU)
        next_btn.get_style_context().add_class("flat")
        next_btn.get_style_context().add_class("cc-search-btn")
        next_btn.set_tooltip_text(_("Next match"))
        next_btn.connect("clicked", lambda *_: self._search_step(forward=True))

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.pack_start(self._search_entry, True, True, 0)
        box.pack_start(prev_btn, False, False, 0)
        box.pack_start(next_btn, False, False, 0)
        bar.add(box)
        bar.connect_entry(self._search_entry)
        bar.set_show_close_button(True)
        bar.connect("notify::search-mode-enabled", self._on_search_mode_changed)
        self.terminal.search_set_wrap_around(True)
        return bar

    def _on_search_mode_changed(self, bar: Gtk.SearchBar, _pspec) -> None:
        if not bar.get_search_mode():
            self.terminal.search_set_gregex(None, 0)
            self.grab_terminal_focus()

    def toggle_search(self) -> None:
        if self._search_bar.get_search_mode():
            self.hide_search()
        else:
            self._search_bar.set_search_mode(True)
            self._search_entry.grab_focus()

    def hide_search(self) -> None:
        self._search_bar.set_search_mode(False)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text()
        if not query:
            self.terminal.search_set_gregex(None, 0)
            return
        pattern = _re.escape(query)
        try:
            regex = GLib.Regex.new(pattern, _SEARCH_FLAGS, GLib.RegexMatchFlags(0))
        except GLib.Error:
            return
        self.terminal.search_set_gregex(regex, 0)
        self._search_step(forward=False)

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
        if font:
            self.terminal.set_font(Pango.FontDescription.from_string(font))
        else:
            self.terminal.set_font(Pango.FontDescription.from_string(_default_font()))
        try:
            self.terminal.set_scrollback_lines(int(settings.get("scrollback") or 10_000))
        except (TypeError, ValueError):
            pass
        theme_name = settings.get("terminal_theme")
        themes.apply_terminal_theme(self.terminal, theme_name)
        self._sync_frame_bg(theme_name)

    def _sync_frame_bg(self, theme_name: str | None) -> None:
        theme = themes.get_theme(theme_name)
        color = Gdk.RGBA()
        if theme and "bg" in theme:
            color.parse(f"#{theme['bg']}")
        else:
            if Gtk.Settings.get_default().get_property("gtk-application-prefer-dark-theme"):
                color.parse("#1a1b26")
            else:
                color.parse("#f5f5f5")
        self._frame.override_background_color(Gtk.StateFlags.NORMAL, color)

    def feed_message(self, text: str) -> None:
        self.terminal.feed(
            f"\r\n{_O}{_B}[ASM]{_R} {text}\r\n".encode()
        )

    def grab_terminal_focus(self) -> None:
        self.terminal.grab_focus()

    def _on_key_pressed(self, _widget, event: Gdk.EventKey) -> bool:
        state = event.state
        keyval = event.keyval
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)

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
