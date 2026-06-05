import json
from datetime import datetime

from meeting_recorder.cli import build_parser, main
from meeting_recorder.organizer import organize_recording
from meeting_recorder.status import CheckItem, EnvironmentReport


def make_meeting(tmp_path, title="Team Sync"):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    return organize_recording(raw, tmp_path / "Meetings", title, dt=datetime(2026, 1, 2, 3, 4, 5))


def test_doctor_command_outputs_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("meeting_recorder.cli.build_environment_report", lambda output_dir: EnvironmentReport([CheckItem("ffmpeg", "pass", "ok")]))

    code = main(["doctor", "--output-dir", str(tmp_path), "--json"])

    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["checks"][0]["name"] == "ffmpeg"


def test_doctor_check_filter(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("meeting_recorder.cli.build_environment_report", lambda output_dir: EnvironmentReport([CheckItem("ffmpeg", "pass", "ok"), CheckItem("display", "error", "bad")]))

    code = main(["status", "--output-dir", str(tmp_path), "--check", "ffmpeg"])

    assert code == 0
    out = capsys.readouterr().out
    assert "ffmpeg" in out
    assert "display" not in out


def test_list_show_commands(tmp_path, capsys):
    meeting = make_meeting(tmp_path)

    assert main(["list", "--output-dir", str(tmp_path / "Meetings")]) == 0
    assert "Team Sync" in capsys.readouterr().out

    assert main(["show", meeting.path.name, "--output-dir", str(tmp_path / "Meetings"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Team Sync"


def test_open_command_opens_summary(monkeypatch, tmp_path, capsys):
    meeting = make_meeting(tmp_path)
    meeting.summary_path.write_text("# Summary", encoding="utf-8")
    opened = []
    monkeypatch.setattr("meeting_recorder.cli.open_path", lambda path: opened.append(path))

    code = main(["open", meeting.path.name, "--output-dir", str(tmp_path / "Meetings"), "--target", "summary"])

    assert code == 0
    assert opened == [meeting.summary_path]
    assert str(meeting.summary_path) in capsys.readouterr().out


def test_export_obsidian_command_writes_note(tmp_path, capsys):
    meeting = make_meeting(tmp_path)
    meeting.transcript_path.write_text("# Transcript\nhello", encoding="utf-8")
    meeting.summary_path.write_text("# Summary\nhello", encoding="utf-8")
    vault = tmp_path / "Vault"

    code = main(["export-obsidian", meeting.path.name, "--output-dir", str(tmp_path / "Meetings"), "--vault", str(vault)])

    assert code == 0
    note_path = capsys.readouterr().out.strip()
    assert note_path.endswith(".md")
    assert "Team Sync" in (vault / "Meetings").glob("*.md").__next__().read_text(encoding="utf-8")


def test_export_ai_prompt_command_writes_codex_prompt(tmp_path, capsys):
    meeting = make_meeting(tmp_path)
    meeting.transcript_path.write_text("# Transcript\nhello", encoding="utf-8")

    code = main(["export-ai-prompt", meeting.path.name, "--output-dir", str(tmp_path / "Meetings"), "--target", "codex"])

    assert code == 0
    prompt_path = meeting.path / "prompt-for-codex.md"
    assert str(prompt_path) in capsys.readouterr().out
    assert "Codex" in prompt_path.read_text(encoding="utf-8")


def test_gui_parser_is_tray_dropdown_only():
    args = build_parser().parse_args(["gui", "--output-dir", "/tmp/meetings"])

    assert args.command == "gui"
    assert not hasattr(args, "mini")
    assert not hasattr(args, "full")
    assert args.output_dir == "/tmp/meetings"


def test_record_start_failure_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("meeting_recorder.cli._has_transcription_engine", lambda: True)
    monkeypatch.setattr("meeting_recorder.cli.start_recording", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no display")))

    code = main(["record", "--output-dir", str(tmp_path), "--json"])

    assert code == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert "no display" in data["error"]


def test_summarize_use_api_missing_env_is_explicit(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("hello", encoding="utf-8")

    code = main(["summarize", "--transcript", str(transcript), "--use-api"])

    assert code == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err
