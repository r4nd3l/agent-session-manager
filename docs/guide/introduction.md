# What is Claude Session Manager?

Claude Session Manager is a native Linux desktop app that gives your
[Claude Code](https://claude.com/claude-code) sessions a proper home.

![Claude Session Manager](https://raw.githubusercontent.com/r4nd3l/claude-session-manager/main/data/screenshot.png)

If you use Claude Code daily, you accumulate **dozens of sessions** scattered
across every project you touch. They live as JSONL transcripts under
`~/.claude/projects/`, named by UUID — there's no overview, no way to name
them, and no quick way to tell which one was which. `claude --resume` only
shows a picker for the current directory.

This app fixes that. It scans every session on your machine, presents them in
a searchable sidebar grouped by project, lets you **name and star** the ones
that matter, and opens any of them in an **embedded terminal tab** that runs
`claude --resume` right where the session started.

::: tip Unofficial community tool
Claude Session Manager is not affiliated with or endorsed by Anthropic. It is
strictly read-only with respect to Claude Code's data — names, favorites, and
all app state live in `~/.config/claude-session-manager/`. Your transcripts
are never modified.
:::

## Why use it?

- **One place for everything.** Every session, every project, newest first —
  instead of UUID-named files and per-directory pickers.
- **Human-readable.** Rename `a3b2152e…` to “JWT auth”, star your daily
  drivers, add an emoji to a tab.
- **Work in parallel.** Open several sessions as tabs. Status dots and desktop
  notifications tell you when a background session has finished.
- **Stay oriented.** Search the sidebar, search a terminal's scrollback, and
  peek at a session's recent messages before resuming it.

## How it compares

Claude Code is a terminal program, and you can absolutely keep using it bare.
Claude Session Manager is a layer *on top* — it doesn't replace the CLI, it
launches and organizes it:

| | Bare `claude --resume` | Claude Session Manager |
| --- | --- | --- |
| See all sessions across projects | ❌ | ✅ |
| Custom names & favorites | ❌ | ✅ |
| Multiple sessions side by side | Manual terminals | ✅ Tabs |
| "Which session was this?" | Read the UUID | ✅ Preview, details, peek |
| Finished-in-the-background alerts | ❌ | ✅ Notifications |

## What's next?

Head to [Getting Started](/guide/getting-started) to install it, or browse the
full [Features](/guide/features).
