from datetime import datetime

from meeting_recorder.ai_export import build_ai_prompt, export_ai_prompt
from meeting_recorder.organizer import organize_recording


def make_meeting(tmp_path, title="Research Sync"):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    meeting = organize_recording(raw, tmp_path / "Meetings", title, dt=datetime(2026, 1, 2, 3, 4, 5))
    meeting.transcript_path.write_text("# Transcript\n[0.0-2.0] We need better follow-up notes.", encoding="utf-8")
    meeting.summary_path.write_text("# Summary\n\n- Existing local summary", encoding="utf-8")
    return meeting


def test_build_ai_prompt_is_claude_codex_ready_and_privacy_explicit(tmp_path):
    meeting = make_meeting(tmp_path)

    prompt = build_ai_prompt(meeting, target="claude-code")

    assert "Claude Code" in prompt
    assert "Research Sync" in prompt
    assert "Create a high-quality meeting summary" in prompt
    assert "Do not claim access to audio/video" in prompt
    assert "We need better follow-up notes" in prompt
    assert "local transcript text" in prompt


def test_export_ai_prompt_writes_prompt_without_credentials(tmp_path):
    meeting = make_meeting(tmp_path)

    prompt_path = export_ai_prompt(meeting, target="codex")

    assert prompt_path == meeting.path / "prompt-for-codex.md"
    text = prompt_path.read_text(encoding="utf-8")
    assert "Codex" in text
    assert "OPENAI_API_KEY" not in text
    assert "ANTHROPIC_API_KEY" not in text
