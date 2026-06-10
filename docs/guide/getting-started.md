# Getting Started

## Requirements

Claude Session Manager is a GTK4 app. You'll need:

- **Python ≥ 3.10**
- **GTK 4**, **libadwaita ≥ 1.5**, **VTE** (the GTK 4 build), and **PyGObject**
- The [`claude` CLI](https://claude.com/claude-code) on your `PATH`

Install the system libraries with your distro's package manager:

::: code-group

```bash [Ubuntu / Debian]
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-vte-3.91
```

```bash [Fedora]
sudo dnf install python3-gobject gtk4 libadwaita vte291-gtk4
```

```bash [Arch]
sudo pacman -S python-gobject gtk4 libadwaita vte4
```

:::

## Install

### Debian / Ubuntu — `.deb`

Grab the latest `.deb` from the
[releases page](https://github.com/r4nd3l/claude-session-manager/releases/latest)
and install it — dependencies are pulled in automatically:

```bash
sudo apt install ./claude-session-manager_*_all.deb
```

It then appears in your app grid as **Claude Session Manager**.

### From source

```bash
git clone https://github.com/r4nd3l/claude-session-manager.git
cd claude-session-manager
python3 -m claude_session_manager
```

To add a desktop launcher and icon for your user:

```bash
./data/install.sh
```

## First run

On first launch the sidebar lists every session found under
`~/.claude/projects/`, with all groups collapsed. Expand a project, click a
session, and it opens in a terminal tab running `claude --resume`. If you
haven't used Claude Code yet, run `claude` in a project once and the session
will show up automatically.
