from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from typing import IO, Literal


@dataclass
class RecorderProcess:
    process: subprocess.Popen
    output_file: Path
    command: list[str]
    stderr_log: Path | None = None
    _stderr_handle: IO[str] | None = None
    paused: bool = False


@dataclass(frozen=True)
class AudioSource:
    name: str
    kind: Literal["system", "mic"]
    backend: Literal["pulse", "alsa"] = "pulse"
    description: str | None = None
    is_default: bool = False
    confidence: Literal["high", "medium", "low"] = "medium"


@dataclass(frozen=True)
class AudioDetection:
    system_sources: list[AudioSource] = field(default_factory=list)
    mic_sources: list[AudioSource] = field(default_factory=list)
    selected_system: AudioSource | None = None
    selected_mic: AudioSource | None = None
    backend_notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def legacy_dict(self) -> dict[str, str | None]:
        return {
            "pulse_monitor": self.selected_system.name if self.selected_system else None,
            "pulse_mic": self.selected_mic.name if self.selected_mic else None,
            "alsa_default": "default",
            "system_audio_backend": self.selected_system.backend if self.selected_system else None,
            "mic_backend": self.selected_mic.backend if self.selected_mic else None,
        }


SCREEN_RE = re.compile(r"dimensions:\s+(\d+x\d+)\s+pixels")
FFMPEG_PULSE_SOURCE_RE = re.compile(r"^\s*\*?\s*([^\s\[]+)(?:\s+\[(.*?)\])?", re.MULTILINE)


def detect_screen_size(display: str | None = None) -> str | None:
    """Best-effort X11 screen-size detection using xdpyinfo."""
    explicit = os.environ.get("MEETING_RECORDER_SIZE")
    if explicit:
        return explicit
    xdpyinfo = shutil.which("xdpyinfo")
    if not xdpyinfo:
        return None
    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    try:
        result = subprocess.run([xdpyinfo], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3, env=env)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    match = SCREEN_RE.search(result.stdout)
    return match.group(1) if match else None


def _pactl_sources(pactl: str) -> list[tuple[str, str | None]]:
    output = subprocess.check_output([pactl, "list", "short", "sources"], text=True, stderr=subprocess.DEVNULL)
    sources: list[tuple[str, str | None]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sources.append((parts[1], parts[4] if len(parts) > 4 else None))
    return sources


def _pactl_default_sink(pactl: str) -> str | None:
    try:
        return subprocess.check_output([pactl, "get-default-sink"], text=True, stderr=subprocess.DEVNULL, timeout=3).strip() or None
    except Exception:
        return None


def parse_ffmpeg_pulse_sources(output: str) -> list[AudioSource]:
    sources: list[AudioSource] = []
    for match in FFMPEG_PULSE_SOURCE_RE.finditer(output):
        name = match.group(1).strip()
        if not name or name.startswith("Auto-detected") or name in {"Cannot", "Failed"}:
            continue
        description = match.group(2)
        kind: Literal["system", "mic"] = "system" if name.endswith(".monitor") else "mic"
        sources.append(AudioSource(name=name, kind=kind, description=description, confidence="medium"))
    return sources


def _ffmpeg_pulse_sources() -> tuple[list[AudioSource], list[str]]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return [], ["ffmpeg not found; cannot enumerate PulseAudio/PipeWire sources"]
    try:
        result = subprocess.run([ffmpeg, "-hide_banner", "-sources", "pulse"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
    except Exception as exc:
        return [], [f"ffmpeg pulse source enumeration failed: {exc}"]
    combined = f"{result.stdout}\n{result.stderr}"
    return parse_ffmpeg_pulse_sources(combined), [] if result.returncode == 0 else [combined.strip()[-500:]]


def detect_audio_sources() -> AudioDetection:
    """Detect PulseAudio/PipeWire-compatible system and microphone sources for ffmpeg."""
    notes: list[str] = []
    errors: list[str] = []
    all_sources: list[AudioSource] = []
    default_monitor: str | None = None
    pactl = shutil.which("pactl")
    if pactl:
        try:
            raw_sources = _pactl_sources(pactl)
            default_sink = _pactl_default_sink(pactl)
            default_monitor = f"{default_sink}.monitor" if default_sink else None
            for name, description in raw_sources:
                kind: Literal["system", "mic"] = "system" if name.endswith(".monitor") else "mic"
                all_sources.append(
                    AudioSource(
                        name=name,
                        kind=kind,
                        description=description,
                        is_default=bool(default_monitor and name == default_monitor),
                        confidence="high" if default_monitor and name == default_monitor else "medium",
                    )
                )
            notes.append("pactl sources detected")
        except Exception as exc:
            errors.append(f"pactl source detection failed: {exc}")
    else:
        notes.append("pactl not found; falling back to ffmpeg PulseAudio/PipeWire source enumeration")

    if not any(src.kind == "system" for src in all_sources):
        ffmpeg_sources, ffmpeg_errors = _ffmpeg_pulse_sources()
        all_sources.extend(ffmpeg_sources)
        errors.extend(ffmpeg_errors)

    system_sources = [src for src in all_sources if src.kind == "system"]
    mic_sources = [src for src in all_sources if src.kind == "mic"]
    selected_system = next((src for src in system_sources if src.is_default), None) or (system_sources[0] if system_sources else None)
    selected_mic = mic_sources[0] if mic_sources else None
    return AudioDetection(system_sources, mic_sources, selected_system, selected_mic, notes, errors)


def detect_audio_inputs() -> dict[str, str | None]:
    """Backward-compatible audio source detection for older callers/tests."""
    return detect_audio_sources().legacy_dict()


def _recording_display(display: str | None = None) -> str:
    selected = display or os.environ.get("DISPLAY")
    if not selected:
        raise RuntimeError("No X11 DISPLAY is set. Set DISPLAY, run under X11/XWayland, or pass --display. Video recording needs this; audio-only recording does not.")
    return selected


def preflight_recording(
    display: str | None = None,
    *,
    include_video: bool = False,
    include_system_audio: bool = True,
    include_mic: bool = True,
) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for recording. Install it with your Linux package manager.")
    if include_video:
        _recording_display(display)
    audio = detect_audio_sources()
    has_selected_system = bool(include_system_audio and audio.selected_system)
    has_selected_mic = bool(include_mic and audio.selected_mic)
    if include_system_audio and not audio.selected_system:
        raise RuntimeError(
            "System audio capture was requested, but no PulseAudio/PipeWire monitor source was detected. "
            "This recording would miss browser/app meeting audio. Install pulseaudio-utils for pactl, ensure pipewire-pulse or pulseaudio is running, then refresh setup; or disable System audio only if you intentionally want mic-only/video-only capture."
        )
    if not include_video and not has_selected_system and not has_selected_mic:
        raise RuntimeError(
            "No recordable input is available for audio-first recording. Enable System audio, enable a detected microphone, or use --video for screen-only capture."
        )
    if include_mic and not audio.selected_mic:
        # Microphone is useful but not the user's stated critical path; ffmpeg will proceed with system audio.
        return


def build_ffmpeg_command(
    output_file: Path,
    fps: int = 15,
    size: str | None = None,
    display: str | None = None,
    include_system_audio: bool = True,
    include_mic: bool = True,
    include_video: bool = False,
) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for recording. Install it with your Linux package manager.")
    audio = detect_audio_sources()
    if include_system_audio and not audio.selected_system:
        raise RuntimeError(
            "System audio capture was requested, but no PulseAudio/PipeWire monitor source was detected. "
            "Your meeting app audio would not be captured."
        )
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "warning"]
    input_index = 0
    video_index: int | None = None
    audio_indexes: list[int] = []

    if include_video:
        selected_display = display or os.environ.get("DISPLAY", ":0.0")
        selected_size = size or detect_screen_size(selected_display) or "1920x1080"
        cmd += ["-f", "x11grab", "-framerate", str(fps), "-video_size", selected_size, "-i", selected_display]
        video_index = input_index
        input_index += 1

    if include_system_audio and audio.selected_system:
        cmd += ["-f", audio.selected_system.backend, "-i", audio.selected_system.name]
        audio_indexes.append(input_index)
        input_index += 1
    if include_mic and audio.selected_mic:
        cmd += ["-f", audio.selected_mic.backend, "-i", audio.selected_mic.name]
        audio_indexes.append(input_index)
        input_index += 1

    if not audio_indexes and video_index is None:
        raise RuntimeError("No recordable inputs were selected or detected. Enable system audio, a detected microphone, or screen video.")

    if video_index is not None:
        cmd += ["-map", f"{video_index}:v", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-vn"]

    if len(audio_indexes) >= 2:
        inputs = "".join(f"[{idx}:a]" for idx in audio_indexes)
        cmd += ["-filter_complex", f"{inputs}amix=inputs={len(audio_indexes)}:duration=longest:dropout_transition=2[a]", "-map", "[a]"]
    elif len(audio_indexes) == 1:
        cmd += ["-map", f"{audio_indexes[0]}:a"]

    if audio_indexes:
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    cmd += [str(output_file)]
    return cmd


def _read_log_tail(path: Path | None, limit: int = 4000) -> str:
    if not path or not path.exists():
        return ""
    data = path.read_text(encoding="utf-8", errors="replace")
    return data[-limit:]


def start_recording(output_file: Path, readiness_timeout: float = 0.75, stderr_log: Path | None = None, **kwargs) -> RecorderProcess:
    output_file = Path(output_file).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    preflight_recording(
        kwargs.get("display"),
        include_video=bool(kwargs.get("include_video", False)),
        include_system_audio=bool(kwargs.get("include_system_audio", True)),
        include_mic=bool(kwargs.get("include_mic", True)),
    )
    cmd = build_ffmpeg_command(output_file, **kwargs)
    if stderr_log is None:
        log_handle = tempfile.NamedTemporaryFile("w", prefix="meeting-recorder-ffmpeg-", suffix=".log", delete=False, encoding="utf-8")
        log_path = Path(log_handle.name)
    else:
        log_path = Path(stderr_log).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_handle, text=True)
    recorder = RecorderProcess(proc, output_file, cmd, log_path, log_handle)
    time.sleep(readiness_timeout)
    code = proc.poll()
    if code is not None:
        log_handle.flush()
        log_handle.close()
        tail = _read_log_tail(log_path)
        raise RuntimeError(f"ffmpeg exited during startup with code {code}. {tail}".strip())
    return recorder


def stop_recording(recorder: RecorderProcess, timeout: int = 10) -> None:
    proc = recorder.process
    if recorder.paused and proc.poll() is None:
        resume_recording(recorder)
    if proc.poll() is None:
        try:
            if proc.stdin:
                proc.stdin.write("q\n")
                proc.stdin.flush()
            proc.wait(timeout=timeout)
        except Exception:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=timeout)
    if recorder._stderr_handle and not recorder._stderr_handle.closed:
        recorder._stderr_handle.flush()
        recorder._stderr_handle.close()
    time.sleep(0.2)


def pause_recording(recorder: RecorderProcess) -> None:
    """Best-effort pause for the ffmpeg process.

    This uses SIGSTOP, so no new samples are encoded while paused. It is Linux
    process-control based rather than a muxer-level segment merge; callers should
    record pause intervals in metadata so the saved duration is honest.
    """

    proc = recorder.process
    if proc.poll() is None and not recorder.paused:
        proc.send_signal(signal.SIGSTOP)
        recorder.paused = True


def resume_recording(recorder: RecorderProcess) -> None:
    proc = recorder.process
    if proc.poll() is None and recorder.paused:
        proc.send_signal(signal.SIGCONT)
        recorder.paused = False
