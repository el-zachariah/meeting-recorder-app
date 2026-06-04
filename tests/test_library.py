import json
from datetime import datetime

import pytest

from meeting_recorder.library import describe_meeting, open_path, resolve_meeting_path, scan_meetings
from meeting_recorder.organizer import organize_recording


def make_meeting(tmp_path, title="Team Sync"):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    return organize_recording(raw, tmp_path / "Meetings", title, dt=datetime(2026, 1, 2, 3, 4, 5))


def test_scan_meetings_reads_metadata_and_artifacts(tmp_path):
    meeting = make_meeting(tmp_path)
    meeting.transcript_path.write_text("hello", encoding="utf-8")

    items = scan_meetings(tmp_path / "Meetings")

    assert len(items) == 1
    assert items[0].title == "Team Sync"
    assert items[0].media_path == meeting.media_path
    assert items[0].transcript_path == meeting.transcript_path
    assert items[0].to_dict()["path"] == str(meeting.path)


def test_scan_meetings_falls_back_without_metadata(tmp_path):
    folder = tmp_path / "Meetings" / "2026-01-01_00-00-00_No-Meta"
    folder.mkdir(parents=True)
    (folder / "recording.webm").write_bytes(b"media")

    item = scan_meetings(tmp_path / "Meetings")[0]

    assert item.title == "No-Meta"
    assert item.created_at == "2026-01-01T00:00:00"
    assert item.media_path == folder / "recording.webm"


def test_resolve_and_describe_meeting_by_prefix(tmp_path):
    meeting = make_meeting(tmp_path, "Planning")

    resolved = resolve_meeting_path(tmp_path / "Meetings", meeting.path.name[:10])
    item = describe_meeting(tmp_path / "Meetings", meeting.path.name)

    assert resolved == meeting.path.resolve()
    assert item.title == "Planning"


def test_resolve_missing_meeting_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_meeting_path(tmp_path / "Meetings", "missing")


def test_open_path_uses_safe_argument_list(tmp_path, monkeypatch):
    target = tmp_path / "folder"
    target.mkdir()
    calls = []

    class DummyPopen:
        def __init__(self, args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr("meeting_recorder.library.subprocess.Popen", DummyPopen)
    open_path(target)

    assert calls[0][0][-1] == str(target.resolve())
    assert isinstance(calls[0][0], list)
