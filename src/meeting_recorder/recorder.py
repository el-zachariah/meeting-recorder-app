from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import signal
import subprocess
import time


@dataclass
class RecorderProcess:
    process: subprocess.Popen
    output_file: Path
    command: list[str]


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
    size = size or os.environ.get("MEETING_RECORDER_SIZE", "1920x1080")
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


def start_recording(output_file: Path, **kwargs) -> RecorderProcess:
    output_file = Path(output_file).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_command(output_file, **kwargs)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return RecorderProcess(proc, output_file, cmd)


def stop_recording(recorder: RecorderProcess, timeout: int = 10) -> None:
    proc = recorder.process
    if proc.poll() is not None:
        return
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
    time.sleep(0.2)
