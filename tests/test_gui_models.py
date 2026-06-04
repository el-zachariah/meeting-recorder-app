from pathlib import Path

from meeting_recorder.gui import format_check_item, format_duration, progress_message, recent_meeting_rows
from meeting_recorder.gui_models import CaptureSelections, SetupGate, bar_geometry, compact_bar_state, popover_geometry, setup_gate_from_report
from meeting_recorder.library import MeetingListItem
from meeting_recorder.status import CheckItem, EnvironmentReport


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


def _report(*checks: CheckItem) -> EnvironmentReport:
    return EnvironmentReport(list(checks))


def test_setup_gate_ready_requires_selected_audio_and_transcriber():
    report = _report(
        CheckItem("ffmpeg", "pass", "ok"),
        CheckItem("output_dir", "pass", "ok"),
        CheckItem("display", "error", "no display"),
        CheckItem("system_audio", "pass", "monitor"),
        CheckItem("microphone", "warn", "no mic"),
        CheckItem("transcription", "pass", "engine", {"whisper_cpp": "/usr/bin/whisper"}),
    )
    gate = setup_gate_from_report(report, CaptureSelections(include_video=False, include_mic=False))
    assert gate.status == "ready"
    assert gate.can_start_selected_config is True


def test_setup_gate_blocks_selected_missing_system_audio():
    report = _report(
        CheckItem("ffmpeg", "pass", "ok"),
        CheckItem("output_dir", "pass", "ok"),
        CheckItem("system_audio", "warn", "no monitor"),
        CheckItem("transcription", "pass", "engine", {"whisper_cpp": "/usr/bin/whisper"}),
    )
    gate = setup_gate_from_report(report, CaptureSelections(include_system_audio=True, transcribe=True))
    assert gate.can_start_selected_config is False
    assert gate.suggested_action == "Record without system audio"
    assert "Ready" not in gate.title


def test_setup_gate_blocks_selected_missing_transcriber():
    report = _report(
        CheckItem("ffmpeg", "pass", "ok"),
        CheckItem("output_dir", "pass", "ok"),
        CheckItem("system_audio", "pass", "monitor"),
        CheckItem("transcription", "warn", "missing", {"whisper_cpp": None, "openai_whisper_cli": None}),
    )
    gate = setup_gate_from_report(report, CaptureSelections(transcribe=True))
    assert gate.can_start_selected_config is False
    assert gate.suggested_action == "Record without transcript"
    assert gate.status == "needs_setup"


def test_compact_bar_state_maps_recording_and_setup():
    assert compact_bar_state(None).label == "Checking setup…"
    blocked = SetupGate(True, False, "blocked", "No input selected", "Pick one", ["No input"], [], "Choose an input")
    assert compact_bar_state(blocked).dot_color == "error"
    needs_setup = SetupGate(True, False, "needs_setup", "Setup needed", "Missing", [], ["Missing"], "Fix")
    assert compact_bar_state(needs_setup).label == "Setup needed"
    recording = compact_bar_state(None, recording=True)
    assert recording.button_text == "Stop"
    assert recording.button_role == "stop"


def test_compact_geometry_helpers_anchor_top_right():
    assert bar_geometry(1920, 1080).endswith("+1506+24")
    assert popover_geometry(1920, 1080).endswith("+1466+80")
