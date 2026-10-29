# How It Works

## Reading sessions

Each supported agent stores its sessions as JSONL transcripts — Claude Code,
for example, writes them under
`~/.claude/projects/<encoded-path>/<uuid>.jsonl`. Agent Session Manager scans
that directory, reads a small prefix of each transcript to extract the project
directory and a message preview, and watches the folder with a
`Gio.FileMonitor` so the list stays live.

It **only reads** these files. The single action that writes to a transcript is
"Move to trash", which sends the file to your system trash (recoverable) behind
a confirmation.

## App state

Custom names, emoji, favorites, hidden sessions, and preferences are stored
separately in `~/.config/agent-session-manager/state.json`. This keeps the
app's data fully decoupled from the agents' own — you can delete the config at
any time without affecting a single session.

## Terminals

Each tab embeds a [VTE](https://gitlab.gnome.org/GNOME/vte) terminal, the same
widget behind GNOME Terminal and Ptyxis. The app spawns your `$SHELL` and types
the agent's command (e.g. `claude --resume <id>`) into it, so your aliases and
environment apply and you drop back to a prompt when the agent exits.

A tab belongs to the **space** of its project folder. A tab can be split into
more panes (a tree of `Gtk.Paned`); the agent's terminal stays the tab's
primary pane, and the extra panes are plain shells in the same folder.

## Agent states

The app watches each agent's terminal and decides what it's doing from what
it shows, never by sending it input:

- **Claude Code** sets the terminal title: a spinner character while it's busy
  (**working**) and `✳` when it's waiting at the prompt. The bottom of the
  screen tells permission prompts and questions apart ("Do you want to
  proceed?", "Enter to select · Esc to cancel"): **blocked**.
- **Cursor** shows "ctrl+c to stop" while busy and prompts such as "Run this
  command?" or "(y) (enter)" when it wants approval.

An agent that goes from working to idle while you're looking at another tab
(or another window) is **done** until you view it. The rules are a simplified
port of [herdr](https://herdr.dev)'s agent-detection manifests (Apache-2.0).
As in herdr, an approval dialog of an unknown shape shows as idle.

## The stack

Agent Session Manager is built with **GTK4**, **libadwaita**, **VTE**, and
**PyGObject**: pure Python, no build step. VTE is the deciding factor: it's the
only production-grade embeddable terminal on Linux, which is why the app is
Linux-native. The data layer (session discovery, parsing, state, agent-state
detection) is GTK-free and unit-tested.

## Architecture

```
claude_session_manager/
├── app.py         # Adw.Application entry point + base CSS
├── window.py      # main window: spaces, tabs, Ctrl+B prefix, actions
├── spaces.py      # spaces / agents sidebar panel and the per-space tab strip
├── panes.py       # split panes inside a tab
├── agentstate.py  # working / blocked / idle detection from title + screen
├── sidebar.py     # the history list
├── store.py       # single source of truth: threaded scans, file monitors
├── models.py      # SessionItem GObject with bindable properties
├── sessions.py    # transcript discovery & parsing (pure Python)
├── providers.py   # per-agent adapters (Claude Code, Cursor)
├── state.py       # app-side persistence
├── terminal.py    # VTE terminal tab
├── themes.py      # color themes and the terminal-workspace stylesheet
├── switcher.py    # quick switcher / go-to-agent picker
├── dialogs.py     # rename / confirm / details / MCP dialogs
└── prefs.py       # preferences dialog
```

The source lives on
[GitHub](https://github.com/r4nd3l/agent-session-manager) under GPL-3.0;
contributions welcome.
