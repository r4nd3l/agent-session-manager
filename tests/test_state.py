import json


def test_roundtrip(app_state):
    state = app_state.AppState()
    state.set_name("sid-1", "My session")
    state.toggle_favorite("sid-1")
    state.set_hidden("sid-2", True)
    state.set_setting("scrollback", 5000)

    fresh = app_state.AppState()
    assert fresh.get_name("sid-1") == "My session"
    assert fresh.is_favorite("sid-1")
    assert fresh.is_hidden("sid-2")
    assert fresh.get_setting("scrollback") == 5000


def test_clearing_name_removes_entry(app_state):
    state = app_state.AppState()
    state.set_name("sid-1", "Name")
    state.set_name("sid-1", "   ")
    assert app_state.AppState().get_name("sid-1") is None


def test_toggle_favorite_returns_new_state(app_state):
    state = app_state.AppState()
    assert state.toggle_favorite("sid") is True
    assert state.toggle_favorite("sid") is False


def test_defaults_for_unknown_settings(app_state):
    state = app_state.AppState()
    assert state.get_setting("color_scheme") == "system"
    assert state.get_setting("font") == ""


def test_corrupt_state_file_recovers(app_state):
    state = app_state.AppState()
    state.set_name("sid", "x")  # creates the file
    app_state._STATE_FILE.write_text("{corrupt", encoding="utf-8")
    fresh = app_state.AppState()  # must not raise
    assert fresh.get_name("sid") is None


def test_migrates_old_config_dir(app_state):
    # state.json in the pre-rebrand dir is carried over to the new dir.
    app_state._OLD_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (app_state._OLD_CONFIG_DIR / "state.json").write_text(
        json.dumps({"names": {"sid": "Carried over"}, "favorites": ["sid"]}),
        encoding="utf-8",
    )
    state = app_state.AppState()
    assert state.get_name("sid") == "Carried over"
    assert state.is_favorite("sid")
    assert app_state._STATE_FILE.exists()  # copied into the new location


def test_migrates_legacy_names_file(app_state):
    app_state._LEGACY_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    app_state._LEGACY_NAMES_FILE.write_text(json.dumps({"old-sid": "Old name"}), encoding="utf-8")
    state = app_state.AppState()
    assert state.get_name("old-sid") == "Old name"
