"""Discover Claude Code sessions from ~/.claude/projects/*/<session-id>.jsonl."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Session transcripts are named <uuid>.jsonl; skip anything else (agent files, etc.)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# How much of a transcript to scan for cwd/preview before giving up.
_MAX_SCAN_LINES = 50
_MAX_SCAN_BYTES = 256 * 1024


@dataclass
class Session:
    session_id: str
    jsonl_path: Path
    cwd: str | None  # project directory recorded in the transcript
    preview: str  # first user message, truncated
    mtime: float  # last activity (file mtime)

    @property
    def project_name(self) -> str:
        if self.cwd:
            return Path(self.cwd).name or self.cwd
        return self.jsonl_path.parent.name

    @property
    def last_active(self) -> datetime:
        return datetime.fromtimestamp(self.mtime)


def _extract_text(content) -> str:
    """Message content is either a plain string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(p for p in parts if p)
    return ""


def _scan_transcript(path: Path) -> tuple[str | None, str]:
    """Return (cwd, preview) from the first lines of a transcript."""
    cwd: str | None = None
    preview = ""
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
                if not isinstance(entry, dict):
                    continue
                if cwd is None and isinstance(entry.get("cwd"), str):
                    cwd = entry["cwd"]
                if not preview and entry.get("type") == "user":
                    message = entry.get("message") or {}
                    text = _extract_text(message.get("content")).strip()
                    # Skip harness-injected content (commands, reminders)
                    if text and not text.startswith("<"):
                        preview = " ".join(text.split())[:120]
                if cwd and preview:
                    break
    except OSError:
        pass
    return cwd, preview


def discover_sessions() -> list[Session]:
    """All sessions under ~/.claude/projects, newest activity first."""
    sessions: list[Session] = []
    if not CLAUDE_PROJECTS_DIR.is_dir():
        return sessions
    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
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
            sessions.append(
                Session(
                    session_id=jsonl.stem,
                    jsonl_path=jsonl,
                    cwd=cwd,
                    preview=preview,
                    mtime=stat.st_mtime,
                )
            )
    sessions.sort(key=lambda s: s.mtime, reverse=True)
    return sessions


@dataclass
class SessionDetails:
    """Full-transcript statistics for the details dialog."""

    user_messages: int = 0
    assistant_messages: int = 0
    tool_calls: int = 0
    models: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    file_size: int = 0


def parse_details(path: Path) -> SessionDetails:
    """Scan the whole transcript. Run off the main thread for big files."""
    details = SessionDetails()
    models: set[str] = set()
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
                ts = entry.get("timestamp")
                if isinstance(ts, str):
                    details.first_timestamp = details.first_timestamp or ts
                    details.last_timestamp = ts
                etype = entry.get("type")
                message = entry.get("message") or {}
                content = message.get("content")
                if etype == "user":
                    if isinstance(content, str):
                        details.user_messages += 1
                    elif isinstance(content, list) and any(
                        isinstance(b, dict) and b.get("type") == "text" for b in content
                    ):
                        details.user_messages += 1
                elif etype == "assistant":
                    details.assistant_messages += 1
                    model = message.get("model")
                    if isinstance(model, str) and not model.startswith("<"):
                        models.add(model)
                    usage = message.get("usage") or {}
                    details.input_tokens += usage.get("input_tokens") or 0
                    details.output_tokens += usage.get("output_tokens") or 0
                    details.cache_read_tokens += usage.get("cache_read_input_tokens") or 0
                    if isinstance(content, list):
                        details.tool_calls += sum(
                            1 for b in content if isinstance(b, dict) and b.get("type") == "tool_use"
                        )
    except OSError:
        pass
    details.models = sorted(models)
    return details
