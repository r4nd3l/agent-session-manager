# Keyboard Shortcuts

## Everywhere

| Shortcut | Action |
| --- | --- |
| `Ctrl+B`, then a key | The prefix commands below |
| `Ctrl+Shift+T` | New session |
| `Ctrl+Shift+N` | New window |
| `Ctrl+Shift+W` | Close the current tab |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Next / previous tab in this space |
| `Ctrl+PgDn` / `Ctrl+PgUp` | Next / previous tab in this space |
| `Ctrl+Shift+K` | Quick switcher: jump to any past session |
| `Ctrl+Shift+F` | Focus the history search |
| `Ctrl+.` | Pick an emoji for the current tab |
| `Ctrl+Shift+E` | Toggle a 😊 on the current tab |
| `F9` | Toggle the sidebar |
| `Ctrl+,` | Preferences |

## In the terminal

| Shortcut | Action |
| --- | --- |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | Copy / paste |
| `Ctrl+Shift+G` | Find in the scrollback |
| `Shift+Enter` | Insert a newline in the agent's prompt |

## The Ctrl+B prefix

Press `Ctrl+B`, release, then press one of these keys. The keys follow
[herdr](https://herdr.dev)'s defaults. A **PREFIX** marker shows in the tab
strip while the prefix waits; any other key cancels it.

| Key | Action |
| --- | --- |
| `v` or `%` | Split right (a shell pane) |
| `-` or `"` | Split down (a shell pane) |
| `h` `j` `k` `l` or arrows | Move to the pane left / below / above / right |
| `Tab` | Next pane |
| `z` | Zoom the pane (again to restore) |
| `x` | Close the pane (on the agent's pane: close the tab) |
| `c` | New agent in this space |
| `n` / `p` | Next / previous tab |
| `1`–`9` | Go to tab 1–9 in this space |
| `N` | New space |
| `T` | Rename the tab |
| `X` | Close the tab |
| `g` | Go to agent |
| `b` | Toggle the sidebar |
| `s` | Preferences |
| `?` | List these keys |
| `Ctrl+B` | Send a literal `Ctrl+B` to the terminal |

`Ctrl+B` is left alone while you type in a search field or a dialog. Agents
that use `Ctrl+B` themselves (Claude Code runs a command in the background
with it) get it by pressing it twice.
