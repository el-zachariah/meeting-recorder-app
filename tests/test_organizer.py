import os
from datetime import datetime
from pathlib import Path

from meeting_recorder.organizer import organize_recording, create_meeting_folder


def test_organize_recording_moves_file_and_writes_metadata(tmp_path):
    src = tmp_path / "raw.mkv"
    src.write_bytes(b"fake media")
    meeting = organize_recording(src, tmp_path / "Meetings", "Team Sync!", dt=datetime(2026, 1, 2, 3, 4, 5))
    assert not src.exists()
    assert meeting.path.name.startswith("2026-01-02_03-04-05_Team-Sync")
    assert meeting.media_path.exists()
    assert meeting.media_path.name == "recording.mkv"
    assert "local-only" in meeting.metadata_path.read_text()


def test_create_meeting_folder_avoids_collisions(tmp_path):
    first = create_meeting_folder(tmp_path, "x", dt=datetime(2026, 1, 1, 0, 0, 0))
    second = create_meeting_folder(tmp_path, "x", dt=datetime(2026, 1, 1, 0, 0, 0))
    assert first.path != second.path
    assert second.path.name.endswith("-2")
