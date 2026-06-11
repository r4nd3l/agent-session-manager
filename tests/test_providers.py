import shutil

from claude_session_manager import providers
from claude_session_manager.providers import (
    ClaudeProvider,
    CursorProvider,
    _decode_cursor_cwd,
    _strip_user_query,
    available_providers,
    get_provider,
)
from claude_session_manager.sessions import discover_sessions

# -- Cursor discovery ---------------------------------------------------------


def test_cursor_discovery(cursor_projects_dir):
    _root, ids = cursor_projects_dir
    sessions = discover_sessions()
    assert {s.session_id for s in sessions} == set(ids.values())
    assert all(s.provider == "cursor" for s in sessions)


def test_cursor_preview_strips_user_query(cursor_projects_dir):
    _root, ids = cursor_projects_dir
    by_id = {s.session_id: s for s in discover_sessions()}
    one = by_id[ids["one"]]
    assert one.preview == "Build foo"
    assert "<user_query>" not in one.preview


def test_cursor_waiting_state(cursor_projects_dir):
    _root, ids = cursor_projects_dir
    by_id = {s.session_id: s for s in discover_sessions()}
    assert by_id[ids["two"]].state == "waiting"  # assistant's last message ends with "?"
    assert by_id[ids["one"]].state == ""


def test_cursor_parse_details(cursor_projects_dir):
    _root, ids = cursor_projects_dir
    by_id = {s.session_id: s for s in discover_sessions()}
    details = CursorProvider().parse_details(by_id[ids["one"]].jsonl_path)
    assert details.user_messages == 1
    assert details.assistant_messages == 1
    # Cursor transcripts carry no token/model data.
    assert details.input_tokens == 0
    assert details.models == []
    assert ("user", "Build foo") in details.messages
    assert ("assistant", "Done.") in details.messages


# -- helpers ------------------------------------------------------------------


def test_strip_user_query():
    assert _strip_user_query("<user_query>\nhi there\n</user_query>") == "hi there"
    assert _strip_user_query("plain text") == "plain text"


def test_decode_cursor_cwd_roundtrip(tmp_path):
    real = tmp_path / "myproj"
    real.mkdir()
    encoded = str(real).lstrip("/").replace("/", "-")
    assert _decode_cursor_cwd(encoded) == str(real)


def test_decode_cursor_cwd_handles_literal_dash(tmp_path):
    real = tmp_path / "a-b-c"
    real.mkdir()
    encoded = str(real).lstrip("/").replace("/", "-")
    assert _decode_cursor_cwd(encoded) == str(real)


def test_decode_cursor_cwd_nonexistent_falls_back():
    assert _decode_cursor_cwd("nope-xyz-qqq") == "/nope/xyz/qqq"


# -- registry + commands ------------------------------------------------------


def test_available_providers_gating(monkeypatch):
    monkeypatch.setattr(providers.ClaudeProvider, "available", lambda self: True)
    monkeypatch.setattr(providers.CursorProvider, "available", lambda self: False)
    assert [p.id for p in available_providers()] == ["claude"]


def test_resume_and_new_commands(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cli: f"/usr/bin/{cli}")
    claude = ClaudeProvider()
    assert claude.resume_command("abc") == "/usr/bin/claude --resume abc"
    assert claude.resume_command("abc", fork=True) == "/usr/bin/claude --resume abc --fork-session"
    cursor = CursorProvider()
    assert cursor.resume_command("xyz") == "/usr/bin/cursor-agent --resume xyz"
    # Cursor doesn't support forking, so --fork-session is never appended.
    assert cursor.resume_command("xyz", fork=True) == "/usr/bin/cursor-agent --resume xyz"
    assert cursor.new_command() == "/usr/bin/cursor-agent"


def test_commands_none_when_cli_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cli: None)
    assert ClaudeProvider().resume_command("abc") is None
    assert ClaudeProvider().new_command() is None


def test_get_provider_default():
    assert get_provider("cursor").id == "cursor"
    assert get_provider("unknown-agent").id == "claude"  # legacy/unknown -> Claude


def test_graceful_exit_text():
    assert ClaudeProvider().graceful_exit() == "/exit\r"
    assert CursorProvider().graceful_exit() is None
