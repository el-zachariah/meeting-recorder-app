from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import os
from pathlib import Path
from typing import Any


APP_ID = "meeting-recorder"


def xdg_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".config"


def settings_path() -> Path:
    return xdg_config_dir() / APP_ID / "settings.json"


@dataclass
class AppSettings:
    default_save_location: str = str(Path.home() / "Meetings")
    transcriber_model: str = "base"
    transcribe_after_recording: bool = True
    summarize_after_transcription: bool = True
    record_system_audio: bool = True
    record_microphone: bool = True
    record_video: bool = False
    fps: int = 15
    size: str = ""
    obsidian_vault: str = ""
    obsidian_folder: str = "Meetings"
    name_saved_folder_by_stop_time: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        valid = {field.name for field in fields(cls)}
        cleaned = {key: value for key, value in data.items() if key in valid}
        settings = cls(**cleaned)
        settings.default_save_location = str(Path(settings.default_save_location).expanduser())
        settings.fps = max(1, min(60, int(settings.fps or 15)))
        return settings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_settings(path: Path | None = None) -> AppSettings:
    path = path or settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppSettings()
    except Exception:
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()
    return AppSettings.from_dict(data)


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
