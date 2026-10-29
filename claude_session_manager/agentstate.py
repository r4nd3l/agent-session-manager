"""Detect what an agent in a terminal is doing from what it shows.

States, as in herdr: "working" (busy), "blocked" (waiting on an approval or a
question), "idle" (ready for input). The window adds "done" (finished while
you weren't looking) on top.

The rules are a simplified port of herdr's agent-detection manifests
(https://herdr.dev, Apache-2.0): the terminal title Claude Code sets, plus the
bottom lines of the visible screen.
"""

from __future__ import annotations

import re

# Claude Code titles: a spinner while busy (Braille, or half-circles since
# 2.1.228), "✳ " when idle.
_CLAUDE_TITLE_WORKING = re.compile(r"^[⠀-⣿◐-◓] ")
_CURSOR_SPINNER = re.compile(r"^\s*[⠀-⣿]+\s+\w+ing\b", re.M)
_CURSOR_ALLOW = re.compile(r"^\s*(?:\S\s*)?(?:allow|run) .*\(y\)", re.M | re.I)
_BACKGROUND_TASKS = re.compile(r"\b[1-9][0-9]*\s+background\s+tasks?\b", re.I)


def _bottom(screen: str, n: int) -> str:
    """The last n non-empty lines, lowercased."""
    lines = [line for line in screen.splitlines() if line.strip()]
    return "\n".join(lines[-n:]).lower()


def _claude(title: str, screen: str) -> str:
    recent = _bottom(screen, 14)
    if "select model" in recent and "enter to set as default" in recent:
        return "idle"  # the /model picker, not a question from the agent
    if (
        "do you want to proceed?" in recent
        or "waiting for permission" in recent
        or "do you want to allow this connection?" in recent
        or "review your answers" in recent
        or ("esc to cancel" in recent
            and ("enter to confirm" in recent or "enter to select" in recent))
        or (("do you want to" in recent or "would you like to" in recent) and "yes" in recent)
    ):
        return "blocked"
    if _CLAUDE_TITLE_WORKING.match(title or "") or "esc to interrupt" in recent:
        return "working"
    return "idle"


def _cursor(screen: str) -> str:
    recent = _bottom(screen, 10)
    if (
        ("run this command?" in recent
         and ("run (once) (y)" in recent or "skip (esc or n)" in recent))
        or ("write to this file?" in recent and "proceed (y)" in recent)
        or "(y) (enter)" in recent
        or "keep (n)" in recent
        or "skip (esc or n)" in recent
        or _CURSOR_ALLOW.search(recent)
    ):
        return "blocked"
    if (
        "ctrl+c to stop" in _bottom(screen, 6)
        or _CURSOR_SPINNER.search(recent)
        or _BACKGROUND_TASKS.search(recent)
    ):
        return "working"
    return "idle"


def detect_state(provider_id: str, title: str, screen: str) -> str:
    """'working' | 'blocked' | 'idle' for an agent's terminal title + screen."""
    if provider_id == "cursor":
        return _cursor(screen)
    if provider_id == "claude":
        return _claude(title, screen)
    return "idle"


def rollup(states: list[str]) -> str:
    """A space's state from its tabs: the most urgent one wins."""
    for state in ("blocked", "working", "done"):
        if state in states:
            return state
    return "idle"
