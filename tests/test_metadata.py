from datetime import datetime
import json

from meeting_recorder.organizer import organize_recording, update_meeting_metadata, rename_meeting_by_end_time


def test_organize_recording_records_default_privacy_metadata(tmp_path):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")

    meeting = organize_recording(raw, tmp_path / "Meetings", "Team Sync", dt=datetime(2026, 1, 2, 3, 4, 5))

    metadata = json.loads(meeting.metadata_path.read_text(encoding="utf-8"))
    assert metadata["network_used"] is False
    assert metadata["provider"] == "local"
    assert metadata["model"] is None
    assert metadata["uploaded_artifacts"] == []


def test_update_meeting_metadata_merges_fields(tmp_path):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    meeting = organize_recording(raw, tmp_path / "Meetings", "Team Sync")

    update_meeting_metadata(meeting, {"ended_at": "2026-01-02T03:30:00", "duration_seconds": 1800})

    metadata = json.loads(meeting.metadata_path.read_text(encoding="utf-8"))
    assert metadata["title"] == "Team Sync"
    assert metadata["ended_at"] == "2026-01-02T03:30:00"
    assert metadata["duration_seconds"] == 1800


def test_rename_meeting_by_end_time_uses_stop_time_and_title(tmp_path):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    meeting = organize_recording(raw, tmp_path / "Meetings", "Draft")

    renamed = rename_meeting_by_end_time(meeting, title="Final Name", ended_at=datetime(2026, 1, 2, 3, 30, 0))

    assert renamed.path.name.startswith("2026-01-02_03-30-00_Final-Name")
    assert renamed.media_path == renamed.path / "recording.mkv"
    metadata = json.loads(renamed.metadata_path.read_text(encoding="utf-8"))
    assert metadata["title"] == "Final Name"
    assert metadata["ended_at"] == "2026-01-02T03:30:00"
