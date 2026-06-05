from pathlib import Path

from meeting_recorder.settings import AppSettings, load_settings, save_settings, settings_path


def test_settings_round_trip_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    expected_path = tmp_path / "config" / "meeting-recorder" / "settings.json"

    settings = AppSettings(default_save_location=str(tmp_path / "Meetings"), transcriber_model="small", record_video=True, fps=30)
    written = save_settings(settings)

    assert written == expected_path
    loaded = load_settings()
    assert loaded.default_save_location == str(tmp_path / "Meetings")
    assert loaded.transcriber_model == "small"
    assert loaded.record_video is True
    assert loaded.fps == 30


def test_settings_ignore_unknown_keys_and_clamp_fps(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"default_save_location":"~/MR","fps":999,"unknown":true}', encoding="utf-8")

    loaded = load_settings(path)

    assert loaded.default_save_location == str(Path("~/MR").expanduser())
    assert loaded.fps == 60
