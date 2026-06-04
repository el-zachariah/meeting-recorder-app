from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import os
import re
import shutil
from typing import Iterable

SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(value: str, default: str = "meeting") -> str:
    value = SAFE_CHARS.sub("-", value.strip()).strip("-._")
    return value[:80] or default


@dataclass(frozen=True)
class MeetingFolder:
    path: Path
    media_path: Path | None
    transcript_path: Path
    summary_path: Path
    metadata_path: Path


def timestamp(dt: datetime | None = None) -> str:
    return (dt or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")


def _unique_folder(base: Path) -> Path:
    counter = 2
    candidate = base
    while candidate.exists():
        candidate = Path(f"{base}-{counter}")
        counter += 1
    return candidate


def create_meeting_folder(base_dir: Path, title: str = "meeting", dt: datetime | None = None) -> MeetingFolder:
    base_dir = Path(base_dir).expanduser().resolve()
    candidate = _unique_folder(base_dir / f"{timestamp(dt)}_{slugify(title)}")
    candidate.mkdir(parents=True, exist_ok=False)
    os.chmod(candidate, 0o700)
    return MeetingFolder(
        path=candidate,
        media_path=None,
        transcript_path=candidate / "transcript.txt",
        summary_path=candidate / "summary.md",
        metadata_path=candidate / "metadata.json",
    )


def default_privacy_metadata() -> dict[str, object]:
    return {
        "privacy": "local-only; no uploads by default",
        "network_used": False,
        "provider": "local",
        "model": None,
        "uploaded_artifacts": [],
    }


def _meeting_with_path(path: Path, media_name: str | None = None) -> MeetingFolder:
    media_path = path / media_name if media_name else None
    if media_path and not media_path.exists():
        media_path = None
    return MeetingFolder(path, media_path, path / "transcript.txt", path / "summary.md", path / "metadata.json")


def read_meeting_metadata(meeting: MeetingFolder | Path) -> dict[str, object]:
    metadata_path = meeting.metadata_path if isinstance(meeting, MeetingFolder) else Path(meeting) / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_meeting_metadata(meeting: MeetingFolder, metadata: dict[str, object]) -> None:
    meeting.metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    os.chmod(meeting.metadata_path, 0o600)


def update_meeting_metadata(meeting: MeetingFolder, updates: dict[str, object]) -> dict[str, object]:
    data = read_meeting_metadata(meeting)
    data.update(updates)
    write_meeting_metadata(meeting, data)
    return data


def organize_recording(
    source_file: Path,
    recordings_dir: Path,
    title: str = "meeting",
    metadata: dict | None = None,
    dt: datetime | None = None,
) -> MeetingFolder:
    meeting = create_meeting_folder(recordings_dir, title, dt)
    source_file = Path(source_file).expanduser().resolve()
    dest = meeting.path / f"recording{source_file.suffix or '.mkv'}"
    if source_file.exists():
        shutil.move(str(source_file), str(dest))
        os.chmod(dest, 0o600)
    else:
        raise FileNotFoundError(source_file)
    data: dict[str, object] = {
        "title": title,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "media_file": dest.name,
    }
    data.update(default_privacy_metadata())
    if metadata:
        data.update(metadata)
    final = MeetingFolder(dest.parent, dest, meeting.transcript_path, meeting.summary_path, meeting.metadata_path)
    write_meeting_metadata(final, data)
    return final


def rename_meeting_by_end_time(meeting: MeetingFolder, title: str, ended_at: datetime) -> MeetingFolder:
    meeting = MeetingFolder(Path(meeting.path), meeting.media_path, meeting.transcript_path, meeting.summary_path, meeting.metadata_path)
    new_base = meeting.path.parent / f"{timestamp(ended_at)}_{slugify(title)}"
    target = _unique_folder(new_base)
    if target != meeting.path:
        meeting.path.rename(target)
    renamed = _meeting_with_path(target, Path(meeting.media_path).name if meeting.media_path else None)
    update_meeting_metadata(
        renamed,
        {
            "title": title,
            "ended_at": ended_at.isoformat(timespec="seconds"),
        },
    )
    return renamed


def list_meetings(recordings_dir: Path) -> Iterable[Path]:
    recordings_dir = Path(recordings_dir).expanduser()
    if not recordings_dir.exists():
        return []
    return sorted([p for p in recordings_dir.iterdir() if p.is_dir()], reverse=True)
