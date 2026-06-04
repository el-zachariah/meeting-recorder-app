import json

from meeting_recorder.status import CheckItem, EnvironmentReport, build_environment_report, format_report_text


def test_environment_report_flags_missing_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.status.shutil.which", lambda name: None)
    monkeypatch.setattr("meeting_recorder.status.detect_screen_size", lambda: None)
    monkeypatch.setattr("meeting_recorder.status.detect_audio_inputs", lambda: {"pulse_monitor": None, "pulse_mic": None, "alsa_default": "default"})
    monkeypatch.setattr("meeting_recorder.status.engine_status", lambda: {"ffmpeg": None, "whisper_cpp": None})
    monkeypatch.setenv("DISPLAY", ":99")

    report = build_environment_report(tmp_path)

    assert not report.ok
    assert any(c.name == "ffmpeg" and c.status == "error" for c in report.checks)
    assert any(c.name == "output_dir" and c.status == "pass" for c in report.checks)
    assert report.to_dict()["privacy_mode"] == "local-only"


def test_format_report_text_contains_actionable_status():
    report = EnvironmentReport([CheckItem("ffmpeg", "error", "install ffmpeg")])
    text = format_report_text(report)
    assert "Meeting Recorder environment doctor" in text
    assert "NEEDS ATTENTION" in text
    assert "[ERROR] ffmpeg: install ffmpeg" in text


def test_report_to_dict_is_json_serializable():
    report = EnvironmentReport([CheckItem("privacy", "pass", "local")])
    encoded = json.dumps(report.to_dict())
    assert "privacy" in encoded
