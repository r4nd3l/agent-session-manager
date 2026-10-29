---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "Agent Session Manager"
  text: "A terminal workspace for your AI coding agents"
  tagline: Run Claude Code and Cursor side by side in spaces, tabs, and split panes. See at a glance which agent is working, which needs you, and which is done, and resume any past session.
  image:
    src: https://raw.githubusercontent.com/r4nd3l/agent-session-manager/main/data/screenshot.png
    alt: Agent Session Manager
  actions:
    - theme: brand
      text: What is it?
      link: /guide/introduction
    - theme: alt
      text: Getting Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/r4nd3l/agent-session-manager

features:
  - icon: 🗂️
    title: Spaces, agents, history
    details: Every project folder you work in is a space with its own tabs. The sidebar lists your spaces, every running agent, and the full history of past sessions.
  - icon: 🚦
    title: Know what every agent is doing
    details: Status dots show whether an agent is working, blocked on your approval, done, or idle, rolled up to its space. Desktop notifications fire when an agent you aren't watching finishes or needs input.
  - icon: 🪟
    title: Split panes & Ctrl+B
    details: Split a tab into shell panes next to the agent. A tmux-style Ctrl+B prefix drives panes, tabs, spaces, and a go-to-agent picker from the keyboard.
  - icon: 🖥️
    title: Real terminals
    details: Each agent runs in an embedded VTE terminal, in its project folder, inside your own shell. Resume any session from the history with one click.
  - icon: 🎨
    title: Themes
    details: A terminal-workspace look in Catppuccin by default, with Tokyo Night, Gruvbox, Nord, Dracula, and more as variants. The classic Adwaita look is one switch away.
  - icon: 🐧
    title: Native GTK4
    details: Built with GTK4, libadwaita, and VTE. Available on the AUR, an Ubuntu PPA, PyPI, and as a .deb. GPL-3.0, open source.
---

## Install

::: code-group

```bash [Arch (AUR)]
yay -S agent-session-manager
```

```bash [Ubuntu (PPA)]
sudo add-apt-repository ppa:matemiller992/agent-session-manager
sudo apt update && sudo apt install agent-session-manager
```

```bash [Debian / Ubuntu (.deb)]
# from the latest GitHub release
sudo apt install ./agent-session-manager_*_all.deb
```

```bash [pipx (any distro)]
pipx install --system-site-packages agent-session-manager-gtk
```

:::

See [Getting Started](/guide/getting-started) for system requirements and
from-source instructions. The installed command is `agent-session-manager`.
