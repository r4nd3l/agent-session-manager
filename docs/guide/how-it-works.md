# How It Works

## Reading sessions

Claude Code stores each session as a JSONL transcript under
`~/.claude/projects/<encoded-path>/<uuid>.jsonl`. Claude Session Manager scans
that directory, reads a small prefix of each transcript to extract the project
directory and a message preview, and watches the folder with a
`Gio.FileMonitor` so the list stays live.

It **only reads** these files. The single action that writes to a transcript is
"Move to trash", which sends the file to your system trash (recoverable) behind
a confirmation.

## App state

Custom names, emoji, favorites, hidden sessions, and preferences are stored
separately in `~/.config/claude-session-manager/state.json`. This keeps the
app's data fully decoupled from Claude Code's — you can delete the config at
any time without affecting a single session.

## Terminals

Each tab embeds a [VTE](https://gitlab.gnome.org/GNOME/vte) terminal — the same
widget behind GNOME Terminal and Ptyxis. The app spawns your `$SHELL` and types
`claude --resume <id>` into it, so your aliases and environment apply and you
drop back to a prompt when Claude exits.

## The stack

Claude Session Manager is built with **GTK4**, **libadwaita**, **VTE**, and
**PyGObject** — pure Python, no build step. VTE is the deciding factor: it's the
only production-grade embeddable terminal on Linux, which is why the app is
Linux-native. The data layer (session discovery, parsing, state) is GTK-free
and unit-tested.

## Architecture

```
claude_session_manager/
├── app.py        # Adw.Application entry point + CSS
├── window.py     # main window: tabs, actions, dialogs wiring
├── sidebar.py    # the session list widget
├── store.py      # single source of truth: threaded scans, file monitors
├── models.py     # SessionItem GObject with bindable properties
├── sessions.py   # transcript discovery & parsing (pure Python)
├── state.py      # app-side persistence
├── terminal.py   # VTE terminal tab
├── dialogs.py    # rename / emoji / confirm / details dialogs
└── prefs.py      # preferences dialog
```

The source lives on
[GitHub](https://github.com/r4nd3l/claude-session-manager) under GPL-3.0 —
contributions welcome.
