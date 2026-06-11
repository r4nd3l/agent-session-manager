"""Built-in terminal color palettes for the VTE terminal."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, Vte  # noqa: E402

# Each theme: foreground, background, and 16 ANSI colors (hex without '#').
# "Default" follows the system / app light-dark scheme (no custom colors).
_THEMES: dict[str, dict | None] = {
    "Default": None,
    "Tango Dark": {
        "fg": "d3d7cf", "bg": "2e3436",
        "palette": ["2e3436", "cc0000", "4e9a06", "c4a000", "3465a4", "75507b",
                    "06989a", "d3d7cf", "555753", "ef2929", "8ae234", "fce94f",
                    "729fcf", "ad7fa8", "34e2e2", "eeeeec"],
    },
    "Solarized Dark": {
        "fg": "839496", "bg": "002b36",
        "palette": ["073642", "dc322f", "859900", "b58900", "268bd2", "d33682",
                    "2aa198", "eee8d5", "002b36", "cb4b16", "586e75", "657b83",
                    "839496", "6c71c4", "93a1a1", "fdf6e3"],
    },
    "Solarized Light": {
        "fg": "657b83", "bg": "fdf6e3",
        "palette": ["073642", "dc322f", "859900", "b58900", "268bd2", "d33682",
                    "2aa198", "eee8d5", "002b36", "cb4b16", "586e75", "657b83",
                    "839496", "6c71c4", "93a1a1", "fdf6e3"],
    },
    "Dracula": {
        "fg": "f8f8f2", "bg": "282a36",
        "palette": ["21222c", "ff5555", "50fa7b", "f1fa8c", "bd93f9", "ff79c6",
                    "8be9fd", "f8f8f2", "6272a4", "ff6e6e", "69ff94", "ffffa5",
                    "d6acff", "ff92df", "a4ffff", "ffffff"],
    },
    "Gruvbox Dark": {
        "fg": "ebdbb2", "bg": "282828",
        "palette": ["282828", "cc241d", "98971a", "d79921", "458588", "b16286",
                    "689d6a", "a89984", "928374", "fb4934", "b8bb26", "fabd2f",
                    "83a598", "d3869b", "8ec07c", "ebdbb2"],
    },
    "Nord": {
        "fg": "d8dee9", "bg": "2e3440",
        "palette": ["3b4252", "bf616a", "a3be8c", "ebcb8b", "81a1c1", "b48ead",
                    "88c0d0", "e5e9f0", "4c566a", "bf616a", "a3be8c", "ebcb8b",
                    "81a1c1", "b48ead", "8fbcbb", "eceff4"],
    },
}

THEME_NAMES = list(_THEMES)
DEFAULT_THEME = "Default"


def _rgba(hex_str: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    color.parse(f"#{hex_str}")
    return color


def apply_terminal_theme(terminal: Vte.Terminal, name: str | None) -> None:
    theme = _THEMES.get(name or DEFAULT_THEME)
    if not theme:  # "Default" / unknown → follow the system colors
        terminal.set_default_colors()
        return
    terminal.set_colors(
        _rgba(theme["fg"]),
        _rgba(theme["bg"]),
        [_rgba(c) for c in theme["palette"]],
    )
