# Claude Session Manager

Native GTK4/libadwaita desktop app to manage [Claude Code](https://claude.com/claude-code) sessions:

- **Sidebar** lists every session found under `~/.claude/projects/`, grouped by project (collapsible headers, with collapse-all/expand-all buttons next to the search box), with a **Favorites** section pinned on top — star a session to move it there. A **search box** filters by name, project, preview, or session id, and the list **updates live** as sessions are created or written to.
- Sessions can be given **custom names** (pencil icon). Names, favorites, and hidden sessions persist in `~/.config/claude-session-manager/state.json` — Claude's own session files are never modified.
- **Clicking a session** opens a tab in the main area; each tab is an embedded **VTE terminal** running your `$SHELL` with `claude --resume <session-id>` typed into it, in the session's original project directory. When claude exits you drop to a shell prompt; the tab closes when the shell exits.
- **Status dots** in the sidebar: green = open in a tab, blue = output arrived in a background tab (the tab also shows an attention marker).
- **Right-click a session** for the full action set: open, open in [Ghostty](https://ghostty.org) (external window — Ghostty can't be embedded), fork (`--fork-session`), rename, favorite, details (messages/models/tokens), copy session id, reveal transcript, hide, or move the transcript to trash.
- **New session** (tab icon in the header) asks for a project folder and starts a fresh `claude` there.
- **Preferences** (menu → Preferences, or `Ctrl+,`): terminal font, scrollback, color scheme.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+F` | Focus search |
| `Ctrl+Shift+T` | New session |
| `Ctrl+Shift+W` | Close current tab |
| `Ctrl+PgUp` / `Ctrl+PgDn` | Previous / next tab |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | Copy / paste in terminal |
| `Ctrl+,` | Preferences |

## Requirements

System packages (Ubuntu 24.04):

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-vte-3.91
```

Plus the `claude` CLI on your `PATH`.

## Run

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
├── eu.zengo.ClaudeSessionManager.desktop   # launcher template
├── icons/eu.zengo.ClaudeSessionManager.svg # app icon
└── install.sh                              # install launcher + icon for current user
```

## Roadmap

- Transcript peek: render last messages in the details dialog
- Drag-and-drop sessions into Favorites
