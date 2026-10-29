# What is Agent Session Manager?

Agent Session Manager is a native Linux desktop app for working with AI coding
agents. It supports [Claude Code](https://claude.com/claude-code) and
[Cursor](https://cursor.com), side by side.

![Agent Session Manager](https://raw.githubusercontent.com/r4nd3l/agent-session-manager/main/data/screenshot.png)

If you use coding agents daily, you end up with several of them running at
once, in different projects, plus **dozens of past sessions** stored as
transcripts named by UUID (Claude Code keeps them under `~/.claude/projects/`).
It's hard to tell which agent is still busy, which one is waiting for your
approval, and which past session was which.

Agent Session Manager gives all of that one home:

- **Spaces.** Every project folder you work in becomes a space with its own
  tabs. Switch spaces from the sidebar; each one remembers the tab you were on.
- **Agents.** Every running agent is listed with a status dot. You can see at a
  glance whether it's **working**, **blocked** on a question or an approval,
  **done** while you were elsewhere, or **idle**.
- **History.** Every past session on your machine, grouped by project and
  searchable. Name and star the ones that matter and resume any of them in a
  terminal tab with one click.
- **Panes.** Split a tab into shell panes next to the agent, and drive
  everything from the keyboard with a tmux-style `Ctrl+B` prefix.

The workspace model and the look are inspired by
[herdr](https://herdr.dev), a terminal workspace manager for coding agents.
Agent Session Manager brings the same way of working to a native GTK app and
adds the session history on top.

::: tip Unofficial community tool
Agent Session Manager is an independent community project, not affiliated with
or endorsed by any agent vendor (including Anthropic) or by herdr. It is
strictly read-only with respect to your agents' data: names, favorites, and
all app state live in `~/.config/agent-session-manager/`. Your transcripts are
never modified.
:::

## Why use it?

- **Run agents in parallel without losing track.** Status dots and desktop
  notifications tell you when an agent finishes or needs your input, so you
  can keep several going at once.
- **One place for every session.** Every session in every project, newest
  first, instead of UUID-named files and per-directory pickers.
- **Human-readable.** Rename `a3b2152e…` to “JWT auth”, star your daily
  drivers, put an emoji on a tab.
- **Keyboard-first when you want it.** Split panes, switch tabs and spaces,
  and jump to any agent with `Ctrl+B`.

## How it compares

Coding agents are terminal programs, and you can keep using them bare. Agent
Session Manager is a layer *on top*: it doesn't replace the CLI, it launches
and organizes it.

| | Bare terminal | Agent Session Manager |
| --- | --- | --- |
| Several agents side by side | Manual windows | ✅ Spaces, tabs, panes |
| Which agent needs me right now? | Check each one | ✅ Status dots + notifications |
| See all past sessions across projects | ❌ | ✅ History |
| Custom names & favorites | ❌ | ✅ |
| "Which session was this?" | Read the UUID | ✅ Preview, details, peek |

## What's next?

Head to [Getting Started](/guide/getting-started) to install it, or browse the
full [Features](/guide/features).
