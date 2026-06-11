"""Agent providers: each adapts one AI coding-agent CLI to the app's Session model.

A provider knows how to discover its sessions on disk, how to resume/start them
in a terminal, and how to close them cleanly. The Claude adapter wraps the
original discovery logic in sessions.py; the Cursor adapter reads cursor-agent's
transcript format (`~/.cursor/projects/<enc-cwd>/agent-transcripts/<uuid>/<uuid>.jsonl`,
top-level `role`, user text wrapped in <user_query> tags, no cwd/usage/timestamps).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
from collections import deque
from pathlib import Path

from . import sessions
from .sessions import (
    _MAX_SCAN_BYTES,
    _MAX_SCAN_LINES,
    _UUID_RE,
    PEEK_MESSAGES,
    Session,
    SessionDetails,
    _extract_text,
    _scan_transcript,
    _tail_state,
)
from .sessions import parse_details as _claude_parse_details

# Cursor transcripts live under ~/.cursor/projects; override for demos/tests.
CURSOR_PROJECTS_DIR = Path(
    os.environ.get("CSM_CURSOR_PROJECTS_DIR") or Path.home() / ".cursor" / "projects"
)

_CURSOR_TAIL_BYTES = 64 * 1024
_USER_QUERY_RE = re.compile(r"</?user_query>")


class Provider:
    """Base class. Subclasses set the class attributes and implement discover()."""

    id: str = ""
    name: str = ""
    cli: str = ""  # executable name looked up on PATH
    icon_name: str = ""  # bundled symbolic icon for sidebar rows
    supports_fork: bool = False

    @property
    def projects_dir(self) -> Path:
        raise NotImplementedError

    def available(self) -> bool:
        return shutil.which(self.cli) is not None

    def watch_dirs(self) -> list[Path]:
        """Directories to file-monitor so the session list stays live.

        Default: the projects dir plus its immediate subdirs (where Claude writes
        its <uuid>.jsonl transcripts).
        """
        base = self.projects_dir
        dirs = [base]
        try:
            dirs += [p for p in base.iterdir() if p.is_dir()]
        except OSError:
            pass
        return dirs

    def discover(self) -> list[Session]:
        raise NotImplementedError

    def resume_command(self, session_id: str, fork: bool = False) -> str | None:
        """Shell command to type into the terminal to resume a session."""
        cli = shutil.which(self.cli)
        if cli is None:
            return None
        cmd = f"{shlex.quote(cli)} --resume {shlex.quote(session_id)}"
        if fork and self.supports_fork:
            cmd += " --fork-session"
        return cmd

    def new_command(self) -> str | None:
        """Shell command to start a fresh session."""
        cli = shutil.which(self.cli)
        return shlex.quote(cli) if cli else None

    def graceful_exit(self) -> str | None:
        """Text to feed the agent to make it exit cleanly, or None to force-close."""
        return None

    def parse_details(self, path: Path) -> SessionDetails:
        raise NotImplementedError


class ClaudeProvider(Provider):
    id = "claude"
    name = "Claude Code"
    cli = "claude"
    icon_name = "agent-claude-symbolic"
    supports_fork = True

    @property
    def projects_dir(self) -> Path:
        # Read live so tests/demos can override sessions.CLAUDE_PROJECTS_DIR.
        return sessions.CLAUDE_PROJECTS_DIR

    def graceful_exit(self) -> str | None:
        return "/exit\r"

    def discover(self) -> list[Session]:
        found: list[Session] = []
        base = self.projects_dir
        if not base.is_dir():
            return found
        for project_dir in base.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl in project_dir.glob("*.jsonl"):
                if not _UUID_RE.match(jsonl.stem):
                    continue
                try:
                    stat = jsonl.stat()
                except OSError:
                    continue
                if stat.st_size == 0:
                    continue
                cwd, preview = _scan_transcript(jsonl)
                found.append(
                    Session(
                        session_id=jsonl.stem,
                        jsonl_path=jsonl,
                        cwd=cwd,
                        preview=preview,
                        mtime=stat.st_mtime,
                        size=stat.st_size,
                        state=_tail_state(jsonl),
                        provider=self.id,
                    )
                )
        return found

    def parse_details(self, path: Path) -> SessionDetails:
        return _claude_parse_details(path)


class CursorProvider(Provider):
    id = "cursor"
    name = "Cursor"
    cli = "cursor-agent"
    icon_name = "agent-cursor-symbolic"
    supports_fork = False

    @property
    def projects_dir(self) -> Path:
        return CURSOR_PROJECTS_DIR

    def watch_dirs(self) -> list[Path]:
        # Cursor nests transcripts one level deeper, under agent-transcripts/,
        # so watch each project's agent-transcripts dir too.
        base = self.projects_dir
        dirs = [base]
        try:
            for project_dir in base.iterdir():
                if not project_dir.is_dir():
                    continue
                dirs.append(project_dir)
                transcripts = project_dir / "agent-transcripts"
                if transcripts.is_dir():
                    dirs.append(transcripts)
        except OSError:
            pass
        return dirs

    def discover(self) -> list[Session]:
        found: list[Session] = []
        base = self.projects_dir
        if not base.is_dir():
            return found
        for project_dir in base.iterdir():
            transcripts = project_dir / "agent-transcripts"
            if not transcripts.is_dir():
                continue
            cwd = _decode_cursor_cwd(project_dir.name)
            for sess_dir in transcripts.iterdir():
                if not sess_dir.is_dir():
                    continue
                jsonl = sess_dir / f"{sess_dir.name}.jsonl"
                if not jsonl.exists():
                    matches = list(sess_dir.glob("*.jsonl"))
                    if not matches:
                        continue
                    jsonl = matches[0]
                try:
                    stat = jsonl.stat()
                except OSError:
                    continue
                if stat.st_size == 0:
                    continue
                found.append(
                    Session(
                        session_id=sess_dir.name,
                        jsonl_path=jsonl,
                        cwd=cwd,
                        preview=_cursor_preview(jsonl),
                        mtime=stat.st_mtime,
                        size=stat.st_size,
                        state=_cursor_state(jsonl),
                        provider=self.id,
                    )
                )
        return found

    def parse_details(self, path: Path) -> SessionDetails:
        return _cursor_parse_details(path)


# -- Cursor parsing helpers ---------------------------------------------------


def _strip_user_query(text: str) -> str:
    """Cursor wraps the human turn in <user_query>…</user_query>."""
    return _USER_QUERY_RE.sub("", text).strip()


def _decode_cursor_cwd(encoded: str) -> str:
    """Reconstruct a cwd from Cursor's dash-encoded project dir name.

    'home-matt-Documents-Git-Foo' -> '/home/matt/Documents/Git/Foo'. Dashes are
    ambiguous (real directories may contain '-'), so walk the real filesystem
    greedily, preferring the longest segment that names an existing directory;
    fall back to a naive '/'-join for the part that no longer exists on disk.
    """
    parts = encoded.split("-")
    path = Path("/")
    i, n = 0, len(parts)
    while i < n:
        best_k: int | None = None
        best_acc: str | None = None
        acc = parts[i]
        k = i
        while k < n:
            if (path / acc).is_dir():
                best_k, best_acc = k, acc
            k += 1
            if k < n:
                acc = acc + "-" + parts[k]
        if best_k is None or best_acc is None:
            return str(path / "/".join(parts[i:]))
        path = path / best_acc
        i = best_k + 1
    return str(path)


def _cursor_preview(path: Path) -> str:
    """First real user message, with <user_query> tags stripped."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            read = 0
            for i, line in enumerate(fh):
                read += len(line)
                if i >= _MAX_SCAN_LINES or read > _MAX_SCAN_BYTES:
                    break
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(entry, dict) or entry.get("role") != "user":
                    continue
                text = _strip_user_query(_extract_text((entry.get("message") or {}).get("content")))
                text = " ".join(text.split())
                if text and not text.startswith("<"):
                    return text[:120]
    except OSError:
        pass
    return ""


def _cursor_state(path: Path) -> str:
    """"waiting" if the agent's last message was a question; else ""."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > _CURSOR_TAIL_BYTES:
                fh.seek(-_CURSOR_TAIL_BYTES, os.SEEK_END)
            blob = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""

    latest: str | None = None
    latest_assistant_text = ""
    for line in blob.splitlines():
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        text = _extract_text((entry.get("message") or {}).get("content")).strip()
        if not text:
            continue
        if role == "assistant":
            latest = "assistant"
            latest_assistant_text = text
        elif role == "user":
            stripped = _strip_user_query(text)
            if stripped and not stripped.startswith("<"):
                latest = "user"

    if latest == "assistant" and latest_assistant_text.rstrip().endswith("?"):
        return "waiting"
    return ""


def _cursor_parse_details(path: Path) -> SessionDetails:
    """Partial details: message counts + recent peek (no tokens/models/timestamps)."""
    details = SessionDetails()
    recent: deque[tuple[str, str]] = deque(maxlen=PEEK_MESSAGES)
    try:
        details.file_size = path.stat().st_size
    except OSError:
        pass
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role")
                text = _extract_text((entry.get("message") or {}).get("content")).strip()
                if role == "user":
                    details.user_messages += 1
                    text = _strip_user_query(text)
                elif role == "assistant":
                    details.assistant_messages += 1
                else:
                    continue
                if text:
                    recent.append((role, " ".join(text.split())))
    except OSError:
        pass
    details.messages = list(recent)
    return details


# -- registry -----------------------------------------------------------------

ALL_PROVIDERS: list[Provider] = [ClaudeProvider(), CursorProvider()]
_BY_ID: dict[str, Provider] = {p.id: p for p in ALL_PROVIDERS}


def get_provider(provider_id: str) -> Provider:
    """Provider for an id, defaulting to Claude for unknown/legacy ids."""
    return _BY_ID.get(provider_id) or _BY_ID["claude"]


def available_providers() -> list[Provider]:
    """Providers whose CLI is installed on PATH."""
    return [p for p in ALL_PROVIDERS if p.available()]
