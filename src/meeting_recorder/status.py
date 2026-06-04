from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
from typing import Iterable

from .recorder import detect_audio_inputs, detect_audio_sources, detect_screen_size
from .transcription import engine_status


@dataclass(frozen=True)
class CheckItem:
    name: str
    status: str  # pass, warn, error
    message: str
    details: dict[str, str | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class EnvironmentReport:
    checks: list[CheckItem]
    privacy_mode: str = "local-only"

    @property
    def ok(self) -> bool:
        return not any(check.status == "error" for check in self.checks)

    def filtered(self, names: Iterable[str]) -> "EnvironmentReport":
        wanted = {name.lower() for name in names}
        return EnvironmentReport([c for c in self.checks if c.name.lower() in wanted], self.privacy_mode)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "privacy_mode": self.privacy_mode,
            "checks": [check.to_dict() for check in self.checks],
        }


def _display_server() -> tuple[str | None, dict[str, str | None]]:
    display = os.environ.get("DISPLAY")
    wayland = os.environ.get("WAYLAND_DISPLAY")
    if display:
        return "x11", {"DISPLAY": display, "WAYLAND_DISPLAY": wayland}
    if wayland:
        return "wayland", {"DISPLAY": display, "WAYLAND_DISPLAY": wayland}
    return None, {"DISPLAY": display, "WAYLAND_DISPLAY": wayland}


def _audio_sources_checks() -> list[CheckItem]:
    detection = detect_audio_sources()
    legacy = detection.legacy_dict()
    details: dict[str, str | bool | None] = {
        **legacy,  # type: ignore[arg-type]
        "system_source_count": str(len(detection.system_sources)),
        "mic_source_count": str(len(detection.mic_sources)),
    }
    if detection.selected_system:
        system = CheckItem("system_audio", "pass", f"System audio monitor detected: {detection.selected_system.name}", details)
    else:
        system = CheckItem(
            "system_audio",
            "warn",
            "No PulseAudio/PipeWire monitor source detected; browser/app meeting audio will not be captured until this is fixed",
            details,
        )
    if detection.selected_mic:
        mic = CheckItem("microphone", "pass", f"Microphone source detected: {detection.selected_mic.name}", details)
    else:
        mic = CheckItem("microphone", "warn", "No microphone source detected", details)
    return [system, mic]


def _audio_sources_check() -> CheckItem:
    audio = detect_audio_inputs()
    found = [key for key in ("pulse_monitor", "pulse_mic") if audio.get(key)]
    if found:
        return CheckItem("audio", "pass", "Audio sources detected", audio)  # type: ignore[arg-type]
    if audio.get("alsa_default"):
        return CheckItem("audio", "warn", "No PulseAudio/PipeWire sources detected; recording may be video-only", audio)  # type: ignore[arg-type]
    return CheckItem("audio", "warn", "No audio sources detected", audio)  # type: ignore[arg-type]


def _output_dir_check(output_dir: Path) -> CheckItem:
    output_dir = Path(output_dir).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".meeting-recorder-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        return CheckItem("output_dir", "error", f"Output directory is not writable: {exc}", {"path": str(output_dir)})
    return CheckItem("output_dir", "pass", "Output directory is writable", {"path": str(output_dir)})


def _tkinter_check() -> CheckItem:
    if importlib.util.find_spec("tkinter") is None:
        return CheckItem("tkinter", "warn", "tkinter is unavailable; CLI will still work")
    try:
        import tkinter  # noqa: F401
    except Exception as exc:
        return CheckItem("tkinter", "warn", f"tkinter import failed: {exc}")
    return CheckItem("tkinter", "pass", "tkinter is available")


def build_environment_report(output_dir: Path | str | None = None) -> EnvironmentReport:
    output_dir = Path(output_dir).expanduser() if output_dir else Path.home() / "Meetings"
    checks: list[CheckItem] = []

    ffmpeg = shutil.which("ffmpeg")
    checks.append(
        CheckItem(
            "ffmpeg",
            "pass" if ffmpeg else "error",
            f"ffmpeg found at {ffmpeg}" if ffmpeg else "ffmpeg is required for recording; install it with your package manager",
            {"path": ffmpeg},
        )
    )

    server, env_details = _display_server()
    if server == "x11":
        checks.append(CheckItem("display", "pass", "X11 display is available", env_details))
    elif server == "wayland":
        checks.append(CheckItem("display", "warn", "Wayland detected; x11grab recording may require an XWayland DISPLAY", env_details))
    else:
        checks.append(CheckItem("display", "warn", "No DISPLAY or WAYLAND_DISPLAY is set; audio-first recording can still work, but optional screen video needs X11/XWayland", env_details))

    size = detect_screen_size()
    checks.append(
        CheckItem(
            "screen_size",
            "pass" if size else "warn",
            f"Detected screen size {size}" if size else "Could not auto-detect screen size; pass --size WIDTHxHEIGHT",
            {"size": size, "xdpyinfo": shutil.which("xdpyinfo")},
        )
    )

    checks.extend(_audio_sources_checks())
    checks.append(_audio_sources_check())
    checks.append(_tkinter_check())

    engines = engine_status()
    available_engines = {k: v for k, v in engines.items() if v and k != "ffmpeg"}
    checks.append(
        CheckItem(
            "transcription",
            "pass" if available_engines else "warn",
            "Local transcription engine detected" if available_engines else "No local transcription engine detected; transcripts will include setup instructions",
            engines,
        )
    )
    checks.append(_output_dir_check(output_dir))
    checks.append(CheckItem("privacy", "pass", "Local-only by default; no uploads unless explicitly requested", {"mode": "local-only"}))
    return EnvironmentReport(checks=checks)


def format_report_text(report: EnvironmentReport) -> str:
    icons = {"pass": "PASS", "warn": "WARN", "error": "ERROR"}
    lines = ["Meeting Recorder environment doctor", f"Overall: {'OK' if report.ok else 'NEEDS ATTENTION'}", f"Privacy: {report.privacy_mode}", ""]
    for check in report.checks:
        lines.append(f"[{icons.get(check.status, check.status.upper())}] {check.name}: {check.message}")
    return "\n".join(lines) + "\n"


def report_to_json(report: EnvironmentReport) -> str:
    return json.dumps(report.to_dict(), indent=2) + "\n"
