# Features

## Sidebar

- **Every session** under `~/.claude/projects/`, **grouped by project** with
  collapsible headers (and collapse-all / expand-all buttons).
- A **Favorites** section pinned on top — star any session to move it there.
- A **search box** that filters by name, project, message preview, or session
  ID, plus a footer showing session, project, transcript-size, and open-tab
  counts.
- **Live updates** — sessions appear and reorder as they're created or written
  to, via a filesystem watch.
- **Quick switcher** (`Ctrl+Shift+K`) — a type-ahead dialog to jump to any
  session by name, project, preview, or ID.
- **Status dots**: green = open in a tab, blue = produced output while in the
  background.

## Custom names, favorites & emoji

- Give any session a **custom name** (pencil icon).
- **Star** sessions to pin them to Favorites.
- Add an **emoji** prefix to a tab (right-click a tab → *Set emoji…*).

All of this is stored in `~/.config/claude-session-manager/state.json`. Claude
Code's own session files are never modified.

## Tabs & terminals

- Clicking a session opens a tab with an embedded **VTE terminal** running your
  `$SHELL` with `claude --resume <id>` in the session's project directory.
- **Per-tab status dots** mirror the sidebar.
- **Rename** tabs, **copy the session ID**, or **fork** a session
  (`--fork-session`) from the right-click menu.
- **Shift+Enter** inserts a newline in Claude's prompt.
- **In-terminal search** (`Ctrl+Shift+G`) over the scrollback.
- Closing a tab asks Claude to **exit cleanly** (`/exit`) in the background
  first, rather than terminating it.
- A **close-all-tabs** button appears when more than one tab is open.

## Knowing what's happening

- **Desktop notifications** when a background session goes quiet after
  producing output — click to jump straight to that tab. (Toggle in
  Preferences.)
- **Session details** (right-click → *Details…*): message and tool-call counts,
  models used, token totals, timestamps, transcript size — plus a **recent
  activity** peek of the last messages, so you can identify a session without
  resuming it.

## Bulk actions & housekeeping

- **Select mode** (checkbox button in the sidebar header) to open, star, hide,
  or trash many sessions at once.
- **Hide** sessions you don't want to see (kept on disk, toggle "Show hidden").
- **Move a transcript to trash** (recoverable) — the only action that touches a
  transcript file, and always behind a confirmation.
- **Open in [Ghostty](https://ghostty.org)** to resume a session in an external
  Ghostty window instead of an embedded tab.

## Preferences

Terminal **font**, **scrollback** size, **color scheme** (system / light /
dark), and the idle-notification toggle — reachable from the menu or `Ctrl+,`.
