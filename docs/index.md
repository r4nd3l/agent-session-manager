---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "Claude Session Manager"
  text: "A native home for your Claude Code sessions"
  tagline: Browse, name, and resume every Claude Code session on your machine — in embedded terminal tabs.
  image:
    src: https://raw.githubusercontent.com/r4nd3l/claude-session-manager/main/data/screenshot.png
    alt: Claude Session Manager
  actions:
    - theme: brand
      text: What is it?
      link: /guide/introduction
    - theme: alt
      text: Getting Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/r4nd3l/claude-session-manager

features:
  - icon: 🗂️
    title: Every session, organized
    details: A sidebar of all your Claude Code sessions, grouped by project, with a pinned Favorites section, live updates, and search.
  - icon: 🖥️
    title: Embedded terminals
    details: Click a session to resume it in a real VTE terminal tab — in its original project directory, inside your own shell.
  - icon: 🏷️
    title: Name & tag freely
    details: Give sessions custom names and tabs emoji prefixes. Everything is stored app-side; Claude Code's own data is never touched.
  - icon: 🔔
    title: Stays out of your way
    details: Status dots and desktop notifications tell you when a background session has finished, so you can work across many at once.
  - icon: 🔍
    title: Find anything
    details: Search the sidebar, search within a terminal's scrollback, and peek at a session's recent messages without resuming it.
  - icon: 🐧
    title: Native GTK4
    details: Built with GTK4, libadwaita, and VTE. Installs as a .deb or runs from source. GPL-3.0, open source.
---
