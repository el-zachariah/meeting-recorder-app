from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .status import EnvironmentReport
from .transcription import engine_status


@dataclass(frozen=True)
class CompactBarState:
    label: str
    dot_color: Literal["success", "warning", "error", "recording", "saving"]
    button_text: str
    button_role: Literal["menu", "stop", "disabled"]
    show_local_badge: bool = True


@dataclass(frozen=True)
class CaptureSelections:
    include_system_audio: bool = True
    include_mic: bool = True
    include_video: bool = False
    transcribe: bool = True
    summarize: bool = True


@dataclass(frozen=True)
class SetupGate:
    can_record: bool
    can_start_selected_config: bool
    status: Literal["checking", "ready", "needs_setup", "blocked", "recording", "saving", "saved"]
    title: str
    message: str
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggested_action: str = "Start Recording"


def _check(report: EnvironmentReport, name: str):
    return next((item for item in report.checks if item.name == name), None)


def has_transcription_engine(details: dict[str, object] | None = None) -> bool:
    data = details if details is not None else engine_status()
    return any(bool(value) for key, value in data.items() if key != "ffmpeg")


def setup_gate_from_report(report: EnvironmentReport, selections: CaptureSelections) -> SetupGate:
    blocking: list[str] = []
    warnings: list[str] = []

    ffmpeg = _check(report, "ffmpeg")
    output_dir = _check(report, "output_dir")
    display = _check(report, "display")
    system_audio = _check(report, "system_audio") or _check(report, "audio")
    microphone = _check(report, "microphone")
    transcription = _check(report, "transcription")

    for item in (ffmpeg, output_dir):
        if item and item.status == "error":
            blocking.append(item.message)

    if selections.include_video and display and (display.status == "error" or not display.details.get("DISPLAY")):
        blocking.append("Video recording is selected, but no X11/XWayland DISPLAY is available.")
    elif selections.include_video and display and display.status == "warn":
        warnings.append(display.message)

    system_audio_ok = bool(system_audio and system_audio.status == "pass")
    if selections.include_system_audio and not system_audio_ok:
        warnings.append("System audio is selected, but no PulseAudio/PipeWire monitor source was found. Meeting app sound will not be captured.")

    mic_ok = bool(microphone and microphone.status == "pass")
    if selections.include_mic and microphone and not mic_ok:
        warnings.append("Microphone is selected, but no microphone source was detected. Your voice may not be captured.")

    transcriber_ok = has_transcription_engine(transcription.details if transcription else None)
    if selections.transcribe and not transcriber_ok:
        warnings.append("Transcription is selected, but no local Whisper-compatible engine is installed.")

    can_record = not blocking
    selected_blockers = list(blocking)
    if selections.include_system_audio and not system_audio_ok:
        selected_blockers.append("Missing system audio monitor source")
    if selections.include_mic and not mic_ok:
        selected_blockers.append("Missing microphone source")
    if not selections.include_video and not (selections.include_system_audio and system_audio_ok) and not (selections.include_mic and mic_ok):
        selected_blockers.append("No recordable input selected or available")
    if selections.transcribe and not transcriber_ok:
        selected_blockers.append("Missing local transcriber")

    if not can_record:
        return SetupGate(False, False, "blocked", "Blocked", "Recording cannot start until setup is fixed.", blocking, warnings, "Fix setup")
    if selections.include_system_audio and not system_audio_ok:
        return SetupGate(True, False, "needs_setup", "Setup needed", warnings[0], selected_blockers, warnings, "Record without system audio")
    if not selections.include_video and not (selections.include_system_audio and system_audio_ok) and not (selections.include_mic and mic_ok):
        return SetupGate(True, False, "blocked", "No input selected", "Enable System audio, choose a detected microphone, or turn on optional screen video before recording.", selected_blockers, warnings, "Choose an input")
    if selections.transcribe and not transcriber_ok:
        return SetupGate(True, False, "needs_setup", "Setup needed", "Local transcriber missing. Recording can be saved, but transcript generation will be skipped unless you install one or record without transcript.", selected_blockers, warnings, "Record without transcript")
    if warnings:
        return SetupGate(True, True, "needs_setup", "Ready with warnings", warnings[0], [], warnings, "Start Recording")
    return SetupGate(True, True, "ready", "Ready", "Ready for local audio-first recording.", [], [], "Start Recording")


def compact_bar_state(gate: SetupGate | None, *, recording: bool = False, busy: bool = False, saved: bool = False) -> CompactBarState:
    if recording:
        return CompactBarState("Recording", "recording", "Stop", "stop")
    if busy:
        return CompactBarState("Saving…", "saving", "…", "disabled")
    if saved:
        return CompactBarState("Saved", "success", "▾", "menu")
    if gate is None:
        return CompactBarState("Checking setup…", "warning", "▾", "menu")
    if gate.status == "ready":
        return CompactBarState("Ready", "success", "▾", "menu")
    if gate.status == "blocked":
        return CompactBarState(gate.title, "error", "▾", "menu")
    return CompactBarState(gate.title, "warning", "▾", "menu")


def bar_geometry(screen_width: int, screen_height: int, width: int = 390, height: int = 48) -> str:
    x = max(24, screen_width - width - 24)
    y = 24
    return f"{width}x{height}+{x}+{y}"


def popover_geometry(screen_width: int, screen_height: int, width: int = 430, height: int = 620) -> str:
    height = min(height, max(360, screen_height - 96))
    x = max(24, screen_width - width - 24)
    y = 80
    return f"{width}x{height}+{x}+{y}"
