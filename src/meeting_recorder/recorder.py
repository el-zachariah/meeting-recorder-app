from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from typing import IO


@dataclass
class RecorderProcess:
    process: subprocess.Popen
    output_file: Path
    command: list[str]
    stderr_log: Path | None = None
    _stderr_handle: IO[str] | None = None


SCREEN_RE = re.compile(r"dimensions:\s+(\d+x\d+)\s+pixels")


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


def detect_audio_inputs() -> dict[str, str | None]:
    """Best-effort Linux audio source detection for ffmpeg."""
    pactl = shutil.which("pactl")
    result: dict[str, str | None] = {"pulse_monitor": None, "pulse_mic": None, "alsa_default": "default"}
    if not pactl:
        return result
    try:
        sources = subprocess.check_output([pactl, "list", "short", "sources"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return result
    for line in sources.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[1]
        if name.endswith(".monitor") and result["pulse_monitor"] is None:
            result["pulse_monitor"] = name
        elif not name.endswith(".monitor") and result["pulse_mic"] is None:
            result["pulse_mic"] = name
    return result


def _recording_display(display: str | None = None) -> str:
    selected = display or os.environ.get("DISPLAY")
    if not selected:
        raise RuntimeError("No X11 DISPLAY is set. Set DISPLAY, run under X11/XWayland, or pass --display.")
    return selected


def preflight_recording(display: str | None = None) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for recording. Install it with your Linux package manager.")
    _recording_display(display)


def build_ffmpeg_command(
    output_file: Path,
    fps: int = 15,
    size: str | None = None,
    display: str | None = None,
    include_system_audio: bool = True,
    include_mic: bool = True,
) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for recording. Install it with your Linux package manager.")
    display = display or os.environ.get("DISPLAY", ":0.0")
    size = size or detect_screen_size(display) or "1920x1080"
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "warning", "-f", "x11grab", "-framerate", str(fps), "-video_size", size, "-i", display]
    audio = detect_audio_inputs()
    audio_inputs = 0
    if include_system_audio and audio.get("pulse_monitor"):
        cmd += ["-f", "pulse", "-i", audio["pulse_monitor"]]
        audio_inputs += 1
    if include_mic and audio.get("pulse_mic"):
        cmd += ["-f", "pulse", "-i", audio["pulse_mic"]]
        audio_inputs += 1
    if audio_inputs >= 2:
        cmd += ["-filter_complex", f"amix=inputs={audio_inputs}:duration=longest:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]"]
    elif audio_inputs == 1:
        cmd += ["-map", "0:v", "-map", "1:a"]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p"]
    if audio_inputs:
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
    preflight_recording(kwargs.get("display"))
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
