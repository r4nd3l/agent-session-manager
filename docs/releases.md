# Releases & Roadmap

A running overview of what's shipped and what's planned. For the full notes and
downloads of each version, see the
[GitHub releases](https://github.com/r4nd3l/agent-session-manager/releases).

## Roadmap

### Shipped milestones

- ✅ **Core** — sidebar of all sessions, embedded terminal tabs, resume/fork
- ✅ **Organization** — favorites, custom names, project groups, search, quick switcher
- ✅ **Insight** — session details, transcript peek, MCP servers & usage, waiting / interrupted badges
- ✅ **Workflow** — idle notifications, graceful `/exit` close, Export as Markdown, tab emoji
- ✅ **Theming** — light/dark plus selectable terminal color palettes
- ✅ **Localization** — English, Hungarian, German, Spanish, French
- ✅ **Multi-window**
- ✅ **Multi-agent** — a provider framework managing Claude Code and Cursor side by side
- ✅ **Native chat** — token-streaming chat with interactive permission cards (Claude) and read-only / trusted Cursor chat; resume any session into a chat
- ✅ **Session replay** — step through a transcript as native chat bubbles
- ✅ **Prompt cards** — answer the agent's questions with native option cards over the terminal
- ✅ **Distribution** — PyPI, AUR, Ubuntu PPA, `.deb`, one-step tag-driven releases
- ✅ **Terminal workspace** — spaces, per-space tabs, split panes, agent states, a `Ctrl+B` prefix, and a herdr-style look with theme variants

### Exploring next

- 🔭 **Agents in split panes** — start an agent (not just a shell) in a pane, with its own state
- 🔭 **Persistent spaces** — keep a space and its layout when its last tab closes, and restore them on restart
- 🔭 **More agents** — additional provider adapters beyond Claude Code and Cursor
- 🔭 **Flathub** distribution

## Changelog

### v1.1.1 — Agent notifications

- **Notifications like herdr's**: when an agent you aren't watching finishes
  or needs your input, you hear a sound and get a notice: an in-app toast
  with a **Show** button while you're in the window, a desktop notification
  otherwise. The sound has its own switch in **Preferences → Notifications**.
- **Fix**: desktop notifications were never shown on some PyGObject versions.

### v1.1.0 — Terminal workspace

The app now works like a terminal workspace for agents, inspired by
[herdr](https://herdr.dev). The previous look stays available as the
*Classic (Adwaita)* interface style.

- **Spaces**: each project folder with open tabs is a space, shown in the
  sidebar with its git branch. Tabs are per space, and the tab strip's **+**
  starts another agent in the same folder.
- **Agents list and states**: every running agent with a status dot:
  **working**, **blocked** (waiting on an approval or a question), **done**
  (finished while you weren't looking), or **idle**, rolled up to its space.
  Detected from Claude Code's terminal title and screen and from Cursor's
  prompts. Notifications fire when an unwatched agent finishes or needs you.
- **Split panes**: shell panes next to the agent, right or down, with
  focus moves, zoom, and close.
- **`Ctrl+B` prefix** with herdr's default keys for panes, tabs, spaces, the
  sidebar, and preferences; `Ctrl+B ?` lists them.
- **Go to agent** picker (`Ctrl+B g`): every running agent, grouped by space,
  filterable by state.
- **Terminal-workspace look**: Catppuccin by default (matching herdr), with
  Tokyo Night, Gruvbox, Nord, Dracula and other variants coloring the whole
  window; framed terminals labelled with their agent.
- **Sidebar**: spaces, agents, and history sections, each foldable and
  switchable in Preferences; the app menu is a ⚙ at the top.
- **Tab emoji picker**: `Ctrl+.` or a click on a tab's emoji opens the picker
  at the tab; one emoji per tab, with a remove button.
- Fixed: the active-tab highlight in the classic style; focus returning to the
  terminal after the quick switcher closes.

### v1.0.0 — Native chat, replay & richer sessions

- **Native streaming chat** (Claude): token-by-token output with **interactive
  permission cards** — Allow / Always allow / Deny every Edit, Write, and Bash.
- **Cursor chat** in read-only (`ask`) and trusted (auto-run) modes.
- **Resume into chat**: reopen any session from the sidebar as a live chat tab.
- **Session replay**: step through any transcript as native chat bubbles.
- **Interactive prompt cards** over the terminal answer the agent's questions
  with a click.
- **Advanced new-session options**: pick a model, permission mode, extra
  directories, or continue the last session in a folder.
- **Open session from file**, **permanent delete** (alongside trash), a
  **folder-path** toggle in the sidebar, and a quick **tab emoji** shortcut
  (`Ctrl+Shift+E`).
- A new **generic agent icon and banner**, replacing the Claude-specific logo.

### v0.10.0 — Multi-agent (Cursor)

- **Provider framework**: session handling is now generalized behind per-agent
  providers, so the app manages more than one AI coding agent.
- **Cursor support**: Cursor sessions are discovered and resumed (`cursor-agent`)
  right alongside Claude Code. One sidebar lists both, each row badged with its
  agent icon.
- **Per-agent New Session**: the New Session menu offers one entry per installed
  agent. Resume, graceful close, and fork all route through each session's own
  agent (Cursor force-closes; fork stays Claude-only).

### v0.9.0 — Rebrand to Agent Session Manager

- Renamed from **Claude Session Manager** to **Agent Session Manager** — the
  project, repository, app icon, and docs — to reflect upcoming support for
  more AI coding agents beyond Claude Code.
- Existing settings, names, and favorites migrate automatically from the old
  `~/.config/claude-session-manager/` location on first run.
- Installed command is now `agent-session-manager`; PyPI package
  `agent-session-manager-gtk`; AUR/PPA package `agent-session-manager`.

### v0.8.0 — Distribution & localization

- **Localization**: full UI translations for Hungarian, German, Spanish, and French, with a language picker
- **Terminal color themes**: Dracula, Solarized, Gruvbox, Nord, Catppuccin, Tokyo Night, Monokai, One Dark…
- **Multi-window** support
- **Interrupted badge** for sessions you stopped mid-task
- **AUR** and **Ubuntu PPA** packages; one-step tag-driven release pipeline

### v0.7.0 — Insight, export & PyPI

- Waiting badge for sessions where Claude asked a question
- Export a session transcript as Markdown
- Published to PyPI; app ID moved to `io.github.r4nd3l.ClaudeSessionManager`

### v0.6.0 — Navigation & config

- Quick switcher (`Ctrl+Shift+K`)
- New Session remembers your last folder; resizable, persisted sidebar
- Drag to reorder tabs; read-only MCP servers browser

### v0.5.0 — Session insight

- Transcript peek in the details dialog
- Desktop notifications when a background session goes idle
- MCP servers and per-session usage; online documentation

### v0.4.0 — Tab usability

- Per-tab emoji, clearer active-tab styling, close-all-tabs button
- Shift+Enter inserts a newline in Claude's prompt

### v0.3.0 — Search & graceful close

- In-terminal find bar; closing a tab asks Claude to exit cleanly (`/exit`)
- Copy session ID; groups collapsed by default; card-style rows

### v0.2.0 — Tabs & workflow

- Renameable tabs, per-tab status dots, toggleable sidebar
- Installable `.deb`

### v0.1.0 — Initial release

- Sidebar of Claude Code sessions, embedded terminal tabs, custom names, favorites
