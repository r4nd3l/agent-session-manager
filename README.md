# Claude Session Manager

[![CI](https://github.com/r4nd3l/claude-session-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/r4nd3l/claude-session-manager/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/claude-session-manager-gtk?label=PyPI)](https://pypi.org/project/claude-session-manager-gtk/)
[![AUR](https://img.shields.io/aur/version/claude-session-manager?label=AUR)](https://aur.archlinux.org/packages/claude-session-manager)
[![Release](https://img.shields.io/github/v/release/r4nd3l/claude-session-manager?label=release)](https://github.com/r4nd3l/claude-session-manager/releases/latest)

Native GTK4/libadwaita desktop app to manage [Claude Code](https://claude.com/claude-code) sessions.

📖 **[Documentation](https://r4nd3l.github.io/claude-session-manager/)**

> **Unofficial community tool.** Not affiliated with or endorsed by Anthropic.
> It never modifies Claude Code's own data — all app state lives in its own config file.

![Claude Session Manager](data/screenshot.png)

Features:

- **Sidebar** lists every session found under `~/.claude/projects/`, grouped by project (collapsible headers, with collapse-all/expand-all buttons next to the search box), with a **Favorites** section pinned on top — star a session to move it there. A **search box** filters by name, project, preview, or session id, and the list **updates live** as sessions are created or written to.
- Sessions can be given **custom names** (pencil icon). Names, favorites, and hidden sessions persist in `~/.config/claude-session-manager/state.json` — Claude's own session files are never modified.
- **Clicking a session** opens a tab in the main area; each tab is an embedded **VTE terminal** running your `$SHELL` with `claude --resume <session-id>` typed into it, in the session's original project directory. When claude exits you drop to a shell prompt; the tab closes when the shell exits. Closing a tab asks Claude to exit cleanly (`/exit`) in the background first.
- **In-terminal search** with a find bar (`Ctrl+Shift+G`) over the tab's scrollback.
- **Status dots** in both the sidebar and on each open tab: green = open, blue = output arrived in a background tab. A **waiting badge** (amber ?) marks sessions where Claude's last message was a question awaiting your reply.
- **Tabs** can be renamed, given an emoji prefix, or have their session ID copied (right-click → Rename… / Set emoji… / Copy session ID); renaming a session's tab updates its name everywhere. A **close-all button** appears when more than one tab is open, and the **sidebar toggles** with the header button or `F9`. **Shift+Enter** inserts a newline in Claude's prompt.
- **Right-click a session** for the full action set: open, open in [Ghostty](https://ghostty.org) (external window — Ghostty can't be embedded), fork (`--fork-session`), rename, favorite, **details** (messages/models/tokens, a peek at recent messages, and MCP servers/usage), copy session id, reveal transcript, hide, or move the transcript to trash.
- **Desktop notifications** when a background session goes quiet after producing output — click to jump to that tab (toggle in Preferences).
- **Select mode** (checkbox button in the sidebar header) for bulk actions: open, star, hide, or trash many sessions at once.
- **New session** (tab icon in the header) asks for a project folder and starts a fresh `claude` there.
- **Quick switcher** (`Ctrl+Shift+K`) jumps to any session by type-ahead; the **New Session** button remembers your last folder; the sidebar is **resizable** and its width is remembered.
- **MCP servers browser** (menu → MCP servers): a read-only view of every MCP server configured in `~/.claude.json`, global and per-project.
- **Preferences** (menu → Preferences, or `Ctrl+,`): terminal font, scrollback, color scheme.
- A status footer shows session, project, transcript-size, and open-tab counts.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+F` | Focus search |
| `Ctrl+Shift+T` | New session |
| `Ctrl+Shift+W` | Close current tab |
| `Ctrl+PgUp` / `Ctrl+PgDn` | Previous / next tab |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | Copy / paste in terminal |
| `Ctrl+Shift+G` | Find in terminal |
| `Ctrl+Shift+K` | Quick switcher (jump to any session) |
| `F9` | Toggle sidebar |
| `Ctrl+,` | Preferences |

## Requirements

Python ≥ 3.10, GTK 4, libadwaita ≥ 1.5, VTE (GTK 4 build), PyGObject — from your distro's packages:

```bash
# Ubuntu / Debian
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-vte-3.91

# Fedora
sudo dnf install python3-gobject gtk4 libadwaita vte291-gtk4

# Arch
sudo pacman -S python-gobject gtk4 libadwaita vte4
```

Plus the [`claude` CLI](https://claude.com/claude-code) on your `PATH`.

> Installing with `pipx`? PyGObject comes from the system, so use
> `pipx install --system-site-packages claude-session-manager-gtk`.

## Install

**Debian/Ubuntu — .deb package** (from the [latest release](https://github.com/r4nd3l/claude-session-manager/releases/latest)):

```bash
sudo apt install ./claude-session-manager_0.7.0_all.deb
```

Dependencies are pulled in automatically; the app appears in your app grid as "Claude Session Manager".

**From source:**

```bash
cd ClaudeSessionManager
python3 -m claude_session_manager
```

Or install the desktop launcher + icon (shows up in the app grid as "Claude Session Manager"):

```bash
./data/install.sh
```

Terminal shortcuts: `Ctrl+Shift+C` copy, `Ctrl+Shift+V` paste.

## Layout

```
claude_session_manager/
├── app.py        # Adw.Application entry point + CSS
├── window.py     # main window: split view, sidebar, tabs, actions, dialogs
├── sessions.py   # session discovery + transcript statistics
├── state.py      # persistent app state (names, favorites, hidden, settings)
├── prefs.py      # preferences dialog
└── terminal.py   # VTE terminal tab spawning the claude CLI
data/
├── io.github.r4nd3l.ClaudeSessionManager.desktop   # launcher template
├── icons/io.github.r4nd3l.ClaudeSessionManager.svg # app icon
└── install.sh                              # install launcher + icon for current user
scripts/
├── build_deb.sh                            # build the .deb package into dist/
└── make_demo_data.py                       # fake sessions for screenshots/demos
```

## Publishing (maintainers)

Publishing a GitHub Release triggers `.github/workflows/publish-pypi.yml`, which
builds the package and uploads it to [PyPI](https://pypi.org/project/claude-session-manager-gtk/)
via **trusted publishing** (OIDC — no API tokens). One-time setup on PyPI:
add a *Trusted Publisher* for the project with owner `r4nd3l`, repository
`claude-session-manager`, and workflow `publish-pypi.yml`.

## Roadmap

- Distribution: AUR, Ubuntu PPA, Flathub
- Optional: terminal color themes, "watch a project", i18n
