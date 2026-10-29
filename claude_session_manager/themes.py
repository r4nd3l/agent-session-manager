"""Built-in color themes: the VTE terminal palettes and, in the TUI style,
the stylesheet that recolors the whole window.

GTK is only imported by the two apply_* functions, so the theme data and the
generated CSS stay testable without it.
"""

from __future__ import annotations

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
    "Catppuccin Mocha": {
        "fg": "cdd6f4", "bg": "1e1e2e",
        "palette": ["45475a", "f38ba8", "a6e3a1", "f9e2af", "89b4fa", "f5c2e7",
                    "94e2d5", "bac2de", "585b70", "f38ba8", "a6e3a1", "f9e2af",
                    "89b4fa", "f5c2e7", "94e2d5", "a6adc8"],
    },
    "Tokyo Night": {
        "fg": "c0caf5", "bg": "1a1b26",
        "palette": ["15161e", "f7768e", "9ece6a", "e0af68", "7aa2f7", "bb9af7",
                    "7dcfff", "a9b1d6", "414868", "f7768e", "9ece6a", "e0af68",
                    "7aa2f7", "bb9af7", "7dcfff", "c0caf5"],
    },
    "Monokai": {
        "fg": "f8f8f2", "bg": "272822",
        "palette": ["272822", "f92672", "a6e22e", "f4bf75", "66d9ef", "ae81ff",
                    "a1efe4", "f8f8f2", "75715e", "f92672", "a6e22e", "f4bf75",
                    "66d9ef", "ae81ff", "a1efe4", "f9f8f5"],
    },
    "One Dark": {
        "fg": "abb2bf", "bg": "282c34",
        "palette": ["282c34", "e06c75", "98c379", "e5c07b", "61afef", "c678dd",
                    "56b6c2", "abb2bf", "5c6370", "e06c75", "98c379", "e5c07b",
                    "61afef", "c678dd", "56b6c2", "ffffff"],
    },
    "Catppuccin Latte": {
        "fg": "4c4f69", "bg": "eff1f5",
        "palette": ["5c5f77", "d20f39", "40a02b", "df8e1d", "1e66f5", "ea76cb",
                    "179299", "acb0be", "6c6f85", "d20f39", "40a02b", "df8e1d",
                    "1e66f5", "ea76cb", "179299", "bcc0cc"],
    },
}

THEME_NAMES = list(_THEMES)
DEFAULT_THEME = "Default"

# Interface styles: "tui" (terminal-workspace look, the whole window takes the
# theme's colors) or "classic" (plain libadwaita).
UI_STYLES = ["tui", "classic"]
DEFAULT_UI_STYLE = "tui"

# Highlight color for the active tab / focused pane; other themes use magenta.
_ACCENTS = {"Catppuccin Mocha": "cba6f7", "Catppuccin Latte": "8839ef", "Dracula": "bd93f9"}


def get_theme(name: str | None) -> dict | None:
    """The palette dict for a theme name, or None for 'Default'/unknown."""
    return _THEMES.get(name or DEFAULT_THEME)


def effective_theme(settings: dict, dark: bool) -> dict | None:
    """The palette actually in use: in the TUI style 'Default' means Catppuccin
    (Mocha or Latte, following the light/dark scheme)."""
    theme = get_theme(settings.get("terminal_theme"))
    if theme is None and settings.get("ui_style", DEFAULT_UI_STYLE) == "tui":
        name = "Catppuccin Mocha" if dark else "Catppuccin Latte"
        theme = {**_THEMES[name], "name": name}
    elif theme is not None:
        theme = {**theme, "name": settings.get("terminal_theme")}
    return theme


# Exact chrome colors for the Catppuccin defaults, so the TUI style matches
# herdr's built-in "catppuccin" theme pixel for pixel. Other themes derive
# these roles by mixing their bg/fg.
_UI_TOKENS = {
    "Catppuccin Mocha": {"mantle": "181825", "surface0": "313244", "surface1": "45475a",
                         "overlay0": "6c7086", "subtext0": "a6adc8"},
    "Catppuccin Latte": {"mantle": "e6e9ef", "surface0": "ccd0da", "surface1": "bcc0cc",
                         "overlay0": "9ca0b0", "subtext0": "6c6f85"},
}


def tui_css(theme: dict) -> str:
    """Stylesheet that recolors libadwaita with the theme and flattens the
    chrome into a terminal-workspace look (herdr's layout and color roles)."""
    bg, fg = f"#{theme['bg']}", f"#{theme['fg']}"
    accent = f"#{_ACCENTS.get(theme.get('name'), theme['palette'][5])}"
    exact = _UI_TOKENS.get(theme.get("name"))
    if exact:
        tokens = {k: f"#{v}" for k, v in exact.items()}
    else:
        tokens = {
            "mantle": f"shade({bg}, 0.85)",
            "surface0": f"mix({bg}, {fg}, 0.12)",
            "surface1": f"mix({bg}, {fg}, 0.2)",
            "overlay0": f"mix({bg}, {fg}, 0.45)",
            "subtext0": f"mix({bg}, {fg}, 0.8)",
        }
    colors = {
        "window_bg_color": bg, "window_fg_color": fg,
        "view_bg_color": bg, "view_fg_color": fg,
        "headerbar_bg_color": tokens["mantle"], "headerbar_fg_color": fg,
        "headerbar_backdrop_color": tokens["mantle"],
        "sidebar_bg_color": tokens["mantle"], "sidebar_fg_color": fg,
        "card_bg_color": tokens["surface0"], "card_fg_color": fg,
        "popover_bg_color": bg, "popover_fg_color": fg,
        "dialog_bg_color": bg, "dialog_fg_color": fg,
        "accent_bg_color": accent, "accent_fg_color": bg, "accent_color": accent,
        "tsm_accent": accent,
        "tsm_green": f"#{theme['palette'][2]}", "tsm_yellow": f"#{theme['palette'][3]}",
        "tsm_red": f"#{theme['palette'][1]}",
        **{f"tsm_{k}": v for k, v in tokens.items()},
    }
    defs = "".join(f"@define-color {k} {v};\n" for k, v in colors.items())
    return defs + """
window { font-family: monospace; }
headerbar { min-height: 34px; box-shadow: none; }
/* libadwaita fades bars to 50% in an unfocused window; a terminal doesn't
   (and the spaces panel / tab strip are bars) */
toolbarview > .top-bar:backdrop > windowhandle,
toolbarview > .bottom-bar:backdrop > windowhandle { filter: none; }

/* flat, rectangular tabs on the panel color; the active one in the accent */
.tab-strip { background-color: @window_bg_color; padding: 2px 6px 0 6px; }
button.strip-tab {
  border-radius: 0;
  min-height: 22px;
  background-color: @tsm_surface0;
  color: @tsm_subtext0;
  box-shadow: none;
}
button.strip-tab:not(.selected) label { opacity: 1; }
button.strip-tab.selected { background-color: @tsm_accent; color: @window_bg_color; }
button.strip-tab.selected label { opacity: 1; }

/* sidebar on the darker mantle; rows are plain text, the current one sits
   on the panel color in full-strength text */
.app-sidebar, .app-sidebar toolbarview, .app-sidebar list,
.app-sidebar scrolledwindow { background-color: @tsm_mantle; }
.app-sidebar row { color: @tsm_subtext0; border-radius: 0; }
.spaces-panel row.current { background-color: @window_bg_color; color: @window_fg_color; }
.app-sidebar .dim-label { color: @tsm_overlay0; opacity: 1; }
.app-sidebar entry { background-color: @tsm_surface0; }
.status-dot.open { background-color: transparent; box-shadow: inset 0 0 0 1.5px @tsm_green; }
.status-dot.attention { background-color: @tsm_yellow; }
/* herdr: ○ idle, ● working / done, ◉ blocked */
.status-dot.idle { background-color: transparent; box-shadow: inset 0 0 0 1.5px @tsm_green; }
.status-dot.working { background-color: @tsm_yellow; }
.status-dot.done { background-color: @tsm_green; box-shadow: none; }
.status-dot.blocked {
  background-color: @tsm_red;
  box-shadow: 0 0 0 2px alpha(@tsm_red, 0.35);
}

/* each terminal sits in a thin frame labelled with its agent */
frame.term-frame {
  border: 1px solid @tsm_surface1;
  border-radius: 0;
  margin: 12px 6px 6px 6px;  /* room for the label above the line */
}
frame.term-frame:focus-within { border-color: @tsm_accent; }
/* pull the label up onto the border line, masking the line behind it */
frame.term-frame > label {
  color: @tsm_accent;
  background-color: @window_bg_color;
  padding: 0 4px;
  margin: -9px 0 0 10px;
}
vte-terminal { padding: 2px 6px; }

entry, row, .count-badge, button.flat { border-radius: 0; }
row.session-child {
  margin-right: 6px;
  background-color: transparent;
  border-left: 1px solid @tsm_surface0;
  border-radius: 0;
}
row.session-child:hover { background-color: @window_bg_color; }
"""


_ui_provider = None  # Gtk.CssProvider while the TUI style is loaded


def apply_ui_style(settings: dict) -> None:
    """(Re)load the app-wide TUI stylesheet; classic style unloads it."""
    from gi.repository import Adw, Gdk, Gtk

    global _ui_provider
    display = Gdk.Display.get_default()
    if _ui_provider is not None:
        Gtk.StyleContext.remove_provider_for_display(display, _ui_provider)
        _ui_provider = None
    if settings.get("ui_style", DEFAULT_UI_STYLE) != "tui":
        return
    theme = effective_theme(settings, Adw.StyleManager.get_default().get_dark())
    _ui_provider = Gtk.CssProvider()
    _ui_provider.load_from_data(tui_css(theme).encode())
    # above the app's base stylesheet (APPLICATION priority) so it wins ties
    Gtk.StyleContext.add_provider_for_display(
        display, _ui_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
    )


def apply_terminal_theme(terminal, settings: dict) -> None:
    """Color a Vte.Terminal with the effective theme."""
    from gi.repository import Adw, Gdk

    def rgba(hex_str: str) -> Gdk.RGBA:
        color = Gdk.RGBA()
        color.parse(f"#{hex_str}")
        return color

    theme = effective_theme(settings, Adw.StyleManager.get_default().get_dark())
    if not theme:  # classic "Default" → follow the system colors
        terminal.set_default_colors()
        return
    terminal.set_colors(rgba(theme["fg"]), rgba(theme["bg"]), [rgba(c) for c in theme["palette"]])
