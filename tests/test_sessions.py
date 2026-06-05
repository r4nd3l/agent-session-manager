from claude_session_manager.sessions import discover_sessions, parse_details


def test_discover_finds_only_real_sessions(projects_dir):
    root, ids = projects_dir
    sessions = discover_sessions()
    assert len(sessions) == 3  # noise files excluded
    assert {s.session_id for s in sessions} == set(ids.values())


def test_discover_extracts_cwd_and_preview(projects_dir):
    _root, ids = projects_dir
    by_id = {s.session_id: s for s in discover_sessions()}
    alpha = by_id[ids["alpha1"]]
    assert alpha.cwd == "/home/user/alpha"
    assert alpha.preview == "Build the alpha feature"
    assert alpha.project_name == "alpha"


def test_discover_sorted_newest_first(projects_dir):
    sessions = discover_sessions()
    mtimes = [s.mtime for s in sessions]
    assert mtimes == sorted(mtimes, reverse=True)


def test_parse_details_counts(projects_dir):
    _root, ids = projects_dir
    session = next(s for s in discover_sessions() if s.session_id == ids["alpha1"])
    details = parse_details(session.jsonl_path)
    assert details.user_messages == 1  # tool_result entry is not a user message
    assert details.assistant_messages == 1
    assert details.tool_calls == 1
    assert details.models == ["claude-opus-4-8"]
    assert details.input_tokens == 100
    assert details.output_tokens == 50
    assert details.cache_read_tokens == 2000
    assert details.first_timestamp == "2026-06-01T10:00:00.000Z"
    assert details.last_timestamp == "2026-06-01T10:01:00.000Z"
    assert details.file_size > 0


def test_parse_details_handles_garbage(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n{\"type\": 12}\n[]\n", encoding="utf-8")
    details = parse_details(bad)
    assert details.user_messages == 0
    assert details.models == []


def test_discover_handles_missing_dir(monkeypatch, tmp_path):
    import claude_session_manager.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "nope")
    assert discover_sessions() == []
