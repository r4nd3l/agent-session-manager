# Features

![The workspace: spaces, agents, and history in the sidebar](/img/main-window.png)

## The workspace

The sidebar has three sections. Click a section's title to fold it; switch
whole sections off in **Preferences → Sidebar**.

- **spaces**: every project folder that has open tabs, with its **git
  branch** underneath. Click a space to switch to it; it reopens the tab you
  were last on there. The **+** starts an agent in a new folder.
- **agents**: every running agent across all spaces, as `space · tab` with the
  agent's name below. Click one to jump straight to it.
- **history**: every past session on your machine (see [History](#history)).

The app menu (Preferences, MCP servers, hidden sessions, open a transcript
file, About) is the **⚙** at the top of the sidebar.

## Agent states

Each agent gets a status dot, in the agents list, on its tab, and rolled up
to its space:

| Dot | State | Meaning |
| --- | --- | --- |
| ● yellow | **working** | The agent is busy (thinking, running tools) |
| ◉ red | **blocked** | It's waiting on you: a permission prompt or a question |
| ● green | **done** | It finished while you weren't looking; clears once you view it |
| ○ green | **idle** | Ready for your next prompt |

A space shows its most urgent agent: blocked, then working, then done.

States are read from what the agent shows: Claude Code's terminal title and
the bottom of the screen (for example "Do you want to proceed?"), or Cursor's
footer and approval prompts. See [How It Works](/guide/how-it-works#agent-states).

**Desktop notifications** fire when an agent you aren't watching finishes or
gets blocked; click one to jump to that tab. Toggle them in Preferences.

## Tabs

- Tabs belong to their space: the tab strip only shows the **current space's
  tabs**. The **+** at the end starts another agent in the same folder.
- Each tab is an embedded **VTE terminal** running your `$SHELL` with the
  agent's command (`claude --resume <id>` to resume a Claude Code session), in
  the project folder.
- **Right-click** a tab to rename it, set or remove its emoji, copy its session
  ID, or close it. **Middle-click** closes it.
- Closing a tab asks the agent to **exit cleanly** (Claude Code's `/exit`) in
  the background first, rather than killing it.
- **In-terminal search** (`Ctrl+Shift+G`) over the scrollback;
  **Shift+Enter** inserts a newline in the agent's prompt.

### Tab emoji

Every tab can carry one emoji. Pick it with **`Ctrl+.`**, from the tab's
right-click menu, or by clicking the emoji already on the tab. The emoji
picker opens right at the tab and applies your pick at once; the button at
the end of its search field removes the emoji. `Ctrl+Shift+E` toggles a 😊.

![Tabs with emoji, the active one highlighted](/img/tab-emoji.png)

## Split panes & the Ctrl+B prefix

Split a tab into **shell panes** in the tab's folder, next to the agent. The
agent stays the tab's main pane; the shells are for running tests, git, or
anything else alongside it. Typing `exit` in a shell pane closes it.

![An agent with a shell pane split to the right](/img/panes.png)

Panes, tabs, and spaces are driven with a **tmux-style prefix**, using the same
keys as herdr: press **`Ctrl+B`**, then a command key. A **PREFIX** marker
shows in the tab strip while it waits. `Ctrl+B ?` lists every key (see
[Keyboard Shortcuts](/guide/keyboard-shortcuts)).

![The Ctrl+B key list](/img/prefix-help.png)

## Go to agent

**`Ctrl+B g`** opens a picker with every running agent, grouped by space and
showing its state. Type to filter by name, space, or state ("blocked" shows
only the agents waiting on you).

![Go to agent](/img/goto.png)

## History

- **Every session** on disk, **grouped by project** with collapsible headers
  (plus collapse-all / expand-all), newest first, updating live as sessions are
  created or written to.
- A **Favorites** group pinned on top; star any session to move it there.
- A **search box** that filters by name, project, message preview, or session
  ID, and a footer with session, project, and transcript-size counts.
- **Waiting badge** (amber **?**): the agent's last message was a question.
  **Interrupted badge** (red stop): you stopped it mid-task.
- Click a session to **resume** it in a tab, in its own space.

![History with the Favorites group expanded](/img/sidebar-favorites.png)

![Searching the history](/img/sidebar-search.png)

**Right-click a session** for the full set of actions: open, open in
[Ghostty](https://ghostty.org), fork (`--fork-session`), continue in chat,
rename, favorite, details, replay, copy session ID, export as Markdown, reveal
the transcript, hide, move to trash, or delete permanently.

**Select mode** (the ✓ button on the history title) opens, stars, hides, or
trashes many sessions at once.

### Quick switcher

`Ctrl+Shift+K` jumps to any past session by type-ahead: arrow keys move,
Enter opens, Esc closes.

![Quick switcher](/img/quick-switcher.png)

## Custom names & favorites

Give any session a **custom name** (pencil icon or right-click → *Rename…*)
and **star** it to pin it to Favorites. Names, favorites, emoji, and hidden
sessions are stored in `~/.config/agent-session-manager/state.json`; your
agents' own session files are never modified.

## Session insight

- **Session details** (right-click → *Details…*): message and tool-call counts,
  models used, token totals, timestamps, transcript size, a peek at the most
  recent messages, and the MCP servers the session could use and actually
  used.

![Session details](/img/session-details.png)

- **MCP servers browser** (⚙ → *MCP servers*): a read-only view of every MCP
  server configured in `~/.claude.json`, global and per-project.

![MCP servers browser](/img/mcp-servers.png)

## Appearance

**Preferences → Appearance → Interface style** chooses between:

- **Terminal workspace** (default): the whole window takes the color theme,
  with flat tabs, framed terminals labelled with their agent, and a monospace
  font throughout.
- **Classic (Adwaita)**: the standard GNOME look, with the same spaces, tabs,
  and panes.

The **color theme** colors the terminals and, in the terminal-workspace style,
the whole window. *Default* is Catppuccin (Mocha in dark mode, Latte in light
mode), matching herdr's default theme. Variants: Tokyo Night, Gruvbox, Nord,
Dracula, Solarized, One Dark, Monokai, Tango.

![The classic Adwaita style](/img/classic.png)

## Preferences

Terminal **font** and **scrollback**, **color scheme** (system / light /
dark), **interface style**, **color theme**, which **sidebar sections** to
show, the **folder path** under history rows, the **language** (English,
Magyar, Deutsch, Español, Français), and **notifications**. Open them from ⚙
or with `Ctrl+,`.

![Preferences](/img/preferences.png)

## Multiple agents

Sessions from every supported agent installed on your machine (currently
**Claude Code** and **Cursor**) are listed together, each badged with its
agent icon, and each resumes with its own agent (`claude --resume` or
`cursor-agent --resume`). The New Session menu offers one entry per installed
agent, plus advanced options (model, permission mode, extra directories,
continue the last session). Closing a Claude tab asks it to `/exit` cleanly;
Cursor tabs close directly; forking is offered where the agent supports it.

## Multiple windows

Open more windows from the New Session menu or with `Ctrl+Shift+N`. Windows
share one session list and state, so names, favorites, and live updates stay
consistent.

## Native chat & replay

Introduced in v1.0 and still available from the New Session menu and a
session's right-click menu:

- **Native chat**: a token-streaming conversation over the agent's headless
  stream-json channel. For Claude, every Edit / Write / Bash pauses on a
  permission card (*Allow once* / *Always allow* / *Deny*); Cursor offers a
  read-only *ask* chat and a *trusted* chat.
- **Session replay**: step through any transcript as chat bubbles.
- **Prompt cards**: when the agent asks a structured question in the
  terminal, a native option card lets you answer with a click.
