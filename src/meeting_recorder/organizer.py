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


def create_meeting_folder(base_dir: Path, title: str = "meeting", dt: datetime | None = None) -> MeetingFolder:
    base_dir = Path(base_dir).expanduser().resolve()
    folder = base_dir / f"{timestamp(dt)}_{slugify(title)}"
    counter = 2
    candidate = folder
    while candidate.exists():
        candidate = Path(f"{folder}-{counter}")
        counter += 1
    candidate.mkdir(parents=True, exist_ok=False)
    os.chmod(candidate, 0o700)
    return MeetingFolder(
        path=candidate,
        media_path=None,
        transcript_path=candidate / "transcript.txt",
        summary_path=candidate / "summary.md",
        metadata_path=candidate / "metadata.json",
    )


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
    data = {
        "title": title,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "media_file": dest.name,
        "privacy": "local-only; no uploads by default",
    }
    if metadata:
        data.update(metadata)
    meeting.metadata_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(meeting.metadata_path, 0o600)
    return MeetingFolder(dest.parent, dest, meeting.transcript_path, meeting.summary_path, meeting.metadata_path)


def list_meetings(recordings_dir: Path) -> Iterable[Path]:
    recordings_dir = Path(recordings_dir).expanduser()
    if not recordings_dir.exists():
        return []
    return sorted([p for p in recordings_dir.iterdir() if p.is_dir()], reverse=True)
