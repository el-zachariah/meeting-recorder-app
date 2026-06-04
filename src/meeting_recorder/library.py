from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import os
import subprocess
from typing import Any

from .organizer import slugify


@dataclass(frozen=True)
class MeetingListItem:
    id: str
    path: Path
    title: str
    created_at: str | None
    media_path: Path | None
    transcript_path: Path | None
    summary_path: Path | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "path": str(self.path),
            "title": self.title,
            "created_at": self.created_at,
            "media_path": str(self.media_path) if self.media_path else None,
            "transcript_path": str(self.transcript_path) if self.transcript_path else None,
            "summary_path": str(self.summary_path) if self.summary_path else None,
            "metadata": self.metadata,
        }


def _read_metadata(folder: Path) -> dict[str, Any]:
    metadata_path = folder / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _created_from_folder(folder: Path) -> str | None:
    prefix = folder.name[:19]
    try:
        return datetime.strptime(prefix, "%Y-%m-%d_%H-%M-%S").isoformat(timespec="seconds")
    except ValueError:
        return None


def _find_media(folder: Path, metadata: dict[str, Any]) -> Path | None:
    media_file = metadata.get("media_file")
    if isinstance(media_file, str) and (folder / media_file).exists():
        return folder / media_file
    for pattern in ("recording.*", "*.mkv", "*.mp4", "*.webm", "*.mov"):
        matches = sorted(folder.glob(pattern))
        if matches:
            return matches[0]
    return None


def _item_from_folder(folder: Path) -> MeetingListItem:
    metadata = _read_metadata(folder)
    title = str(metadata.get("title") or folder.name[20:] or folder.name)
    created_at = str(metadata.get("created_at") or _created_from_folder(folder) or "") or None
    transcript = folder / "transcript.txt"
    summary = folder / "summary.md"
    return MeetingListItem(
        id=folder.name,
        path=folder,
        title=title,
        created_at=created_at,
        media_path=_find_media(folder, metadata),
        transcript_path=transcript if transcript.exists() else None,
        summary_path=summary if summary.exists() else None,
        metadata=metadata,
    )


def scan_meetings(recordings_dir: Path | str, limit: int | None = None) -> list[MeetingListItem]:
    base = Path(recordings_dir).expanduser()
    if not base.exists():
        return []
    folders = [p for p in base.iterdir() if p.is_dir()]
    folders.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    items = [_item_from_folder(folder) for folder in folders]
    return items[:limit] if limit else items


def resolve_meeting_path(recordings_dir: Path | str, meeting: str | Path) -> Path:
    candidate = Path(meeting).expanduser()
    if candidate.exists():
        return candidate.resolve()
    base = Path(recordings_dir).expanduser()
    token = str(meeting)
    exact = base / token
    if exact.exists():
        return exact.resolve()
    matches = [item.path for item in scan_meetings(base) if item.id.startswith(token) or slugify(item.title).lower().startswith(slugify(token).lower())]
    if not matches:
        raise FileNotFoundError(f"No meeting found for {meeting!s}")
    if len(matches) > 1:
        raise ValueError(f"Meeting identifier {meeting!s} is ambiguous")
    return matches[0].resolve()


def describe_meeting(recordings_dir: Path | str, meeting: str | Path) -> MeetingListItem:
    path = resolve_meeting_path(recordings_dir, meeting)
    if not path.is_dir():
        raise NotADirectoryError(path)
    return _item_from_folder(path)


def open_path(path: Path | str) -> subprocess.Popen:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    opener = "open" if os.name == "darwin" else "xdg-open"
    return subprocess.Popen([opener, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
