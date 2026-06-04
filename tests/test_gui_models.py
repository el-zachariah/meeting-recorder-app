from pathlib import Path

from meeting_recorder.gui import format_check_item, format_duration, progress_message, recent_meeting_rows
from meeting_recorder.library import MeetingListItem
from meeting_recorder.status import CheckItem


def test_format_duration():
    assert format_duration(0) == "00:00"
    assert format_duration(65) == "01:05"
    assert format_duration(3661) == "1:01:01"
    assert format_duration(-5) == "00:00"


def test_format_check_item_is_headless_safe():
    check = CheckItem("ffmpeg", "pass", "found")
    assert format_check_item(check) == "✓ ffmpeg: found"


def test_progress_message_known_and_unknown():
    assert "Recording" in progress_message("recording")
    assert progress_message("custom") == "custom"


def test_recent_meeting_rows_are_plain_data():
    item = MeetingListItem(
        id="2026-01-02_03-04-05-team-sync",
        path=Path("/tmp/meeting"),
        title="Team Sync",
        created_at="2026-01-02T03:04:05",
        media_path=Path("/tmp/meeting/recording.mkv"),
        transcript_path=Path("/tmp/meeting/transcript.txt"),
        summary_path=None,
        metadata={},
    )

    rows = recent_meeting_rows([item])

    assert rows[0].title == "Team Sync"
    assert rows[0].has_transcript is True
    assert rows[0].has_summary is False
