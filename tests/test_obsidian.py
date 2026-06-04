from datetime import datetime
import json

from meeting_recorder.obsidian import build_obsidian_note, export_meeting_to_obsidian
from meeting_recorder.organizer import organize_recording


def make_meeting(tmp_path, title="Team Sync"):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    meeting = organize_recording(
        raw,
        tmp_path / "Meetings",
        title,
        metadata={
            "started_at": "2026-01-02T03:00:00",
            "ended_at": "2026-01-02T03:30:00",
            "duration_seconds": 1800,
            "network_used": False,
            "provider": "local",
            "model": "base",
            "uploaded_artifacts": [],
        },
        dt=datetime(2026, 1, 2, 3, 4, 5),
    )
    meeting.transcript_path.write_text("# Transcript\n[0.0-1.0] Hello team", encoding="utf-8")
    meeting.summary_path.write_text("# Summary\n\n## Key points\n- We decided to ship.", encoding="utf-8")
    return meeting


def test_build_obsidian_note_contains_frontmatter_and_links(tmp_path):
    meeting = make_meeting(tmp_path)

    note = build_obsidian_note(meeting)

    assert note.startswith("---\n")
    assert "title: Team Sync" in note
    assert "network_used: false" in note
    assert "provider: local" in note
    assert "# Team Sync" in note
    assert "## Summary" in note
    assert "file://" in note
    assert "transcript.txt" in note


def test_export_meeting_to_obsidian_writes_sanitized_stop_time_note(tmp_path):
    meeting = make_meeting(tmp_path, "Team Sync / Planning")
    vault = tmp_path / "Vault"

    note_path = export_meeting_to_obsidian(meeting, vault, folder="Meetings")

    assert note_path.exists()
    assert note_path.parent == vault / "Meetings"
    assert note_path.name.startswith("2026-01-02_03-30-00_Team-Sync-Planning")
    text = note_path.read_text(encoding="utf-8")
    assert "Team Sync / Planning" in text
    assert "recording.mkv" in text


def test_export_meeting_to_obsidian_can_copy_text_artifacts(tmp_path):
    meeting = make_meeting(tmp_path)
    vault = tmp_path / "Vault"

    note_path = export_meeting_to_obsidian(meeting, vault, folder="Meetings", copy_text_artifacts=True)

    copied_transcript = note_path.parent / "assets" / meeting.path.name / "transcript.txt"
    copied_summary = note_path.parent / "assets" / meeting.path.name / "summary.md"
    assert copied_transcript.exists()
    assert copied_summary.exists()
    assert "assets/" in note_path.read_text(encoding="utf-8")


def test_obsidian_export_does_not_copy_media_by_default(tmp_path):
    meeting = make_meeting(tmp_path)
    vault = tmp_path / "Vault"

    note_path = export_meeting_to_obsidian(meeting, vault)

    assert not list((note_path.parent / "assets").glob("**/*.mkv")) if (note_path.parent / "assets").exists() else True
    metadata = json.loads(meeting.metadata_path.read_text(encoding="utf-8"))
    assert metadata["network_used"] is False
