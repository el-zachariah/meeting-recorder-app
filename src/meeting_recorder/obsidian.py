from __future__ import annotations

from pathlib import Path
import shutil

from .organizer import MeetingFolder, read_meeting_metadata, slugify


def _yaml_scalar(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\n", " ").strip()
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", "[", "]", "{", "}", "\"", "'"]) or text.lower() in {"true", "false", "null"}:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _file_uri(path: Path) -> str:
    return path.expanduser().resolve().as_uri()


def _read_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _duration_label(seconds: object) -> str:
    try:
        total = int(seconds)  # type: ignore[arg-type]
    except Exception:
        return "unknown"
    minutes, secs = divmod(max(0, total), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _relative_or_uri(path: Path, vault_path: Path) -> str:
    try:
        return path.resolve().relative_to(vault_path.resolve()).as_posix()
    except ValueError:
        return _file_uri(path)


def build_obsidian_note(
    meeting: MeetingFolder,
    vault_path: Path | None = None,
    transcript_link_path: Path | None = None,
    summary_link_path: Path | None = None,
    media_link_path: Path | None = None,
) -> str:
    metadata = read_meeting_metadata(meeting)
    title = str(metadata.get("title") or meeting.path.name[20:] or meeting.path.name)
    started = metadata.get("started_at") or metadata.get("created_at") or ""
    ended = metadata.get("ended_at") or ""
    duration = _duration_label(metadata.get("duration_seconds"))
    media_target = media_link_path or meeting.media_path
    transcript_target = transcript_link_path or meeting.transcript_path
    summary_target = summary_link_path or meeting.summary_path
    media_link = _relative_or_uri(media_target, vault_path) if media_target and vault_path else (_file_uri(media_target) if media_target else "")
    transcript_link = _relative_or_uri(transcript_target, vault_path) if transcript_target.exists() and vault_path else (_file_uri(transcript_target) if transcript_target.exists() else "")
    summary_link = _relative_or_uri(summary_target, vault_path) if summary_target.exists() and vault_path else (_file_uri(summary_target) if summary_target.exists() else "")
    summary = _read_if_exists(meeting.summary_path)
    transcript = _read_if_exists(meeting.transcript_path)

    frontmatter = {
        "type": "meeting",
        "title": title,
        "created": metadata.get("created_at") or "",
        "started": started,
        "ended": ended,
        "duration": duration,
        "source": "meeting-recorder",
        "privacy": metadata.get("privacy") or "local-first",
        "network_used": metadata.get("network_used", False),
        "provider": metadata.get("provider") or "local",
        "model": metadata.get("model"),
        "recording": media_link,
    }
    yaml = "---\n" + "".join(f"{key}: {_yaml_scalar(value)}\n" for key, value in frontmatter.items()) + "---\n"
    return f"""{yaml}
# {title}

> Created by Meeting Recorder. Default privacy mode is local-first; network AI is used only when explicitly enabled.

## Summary

{summary or '_No summary generated yet._'}

## Decisions

- _Add decisions here._

## Action items

- _Add follow-up tasks here._

## Transcript

{transcript or '_No transcript generated yet._'}

## Files

- Recording: {media_link or '_missing_'}
- Transcript: {transcript_link or '_missing_'}
- Summary: {summary_link or '_missing_'}
"""


def _note_name(meeting: MeetingFolder) -> str:
    metadata = read_meeting_metadata(meeting)
    when = str(metadata.get("ended_at") or metadata.get("created_at") or "")[:19].replace("T", "_").replace(":", "-")
    if not when or len(when) < 19:
        when = meeting.path.name[:19]
    title = str(metadata.get("title") or meeting.path.name[20:] or "meeting")
    return f"{when}_{slugify(title)}.md"


def _copy_text_artifacts(meeting: MeetingFolder, note_dir: Path) -> dict[str, Path]:
    asset_dir = note_dir / "assets" / meeting.path.name
    asset_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for key, src in (("transcript", meeting.transcript_path), ("summary", meeting.summary_path)):
        if src.exists():
            dest = asset_dir / src.name
            shutil.copy2(src, dest)
            copied[key] = dest
    return copied


def _safe_vault_subdir(vault_path: Path, folder: str) -> Path:
    original = folder.strip()
    if Path(original).is_absolute():
        raise ValueError("Obsidian folder must be a relative path inside the vault")
    raw = original.strip("/") or "Meetings"
    folder_path = Path(raw)
    if folder_path.is_absolute() or any(part in {"..", ""} for part in folder_path.parts):
        raise ValueError("Obsidian folder must be a relative path inside the vault")
    note_dir = (vault_path / folder_path).resolve()
    if not note_dir.is_relative_to(vault_path):
        raise ValueError("Obsidian folder must stay inside the vault")
    return note_dir


def export_meeting_to_obsidian(
    meeting: MeetingFolder,
    vault_path: Path,
    folder: str = "Meetings",
    copy_media: bool = False,
    copy_text_artifacts: bool = False,
) -> Path:
    vault_path = Path(vault_path).expanduser().resolve()
    note_dir = _safe_vault_subdir(vault_path, folder)
    note_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    if copy_text_artifacts:
        copied = _copy_text_artifacts(meeting, note_dir)
    media_copy: Path | None = None
    if copy_media and meeting.media_path and meeting.media_path.exists():
        asset_dir = note_dir / "assets" / meeting.path.name
        asset_dir.mkdir(parents=True, exist_ok=True)
        media_copy = asset_dir / meeting.media_path.name
        shutil.copy2(meeting.media_path, media_copy)
    note_path = note_dir / _note_name(meeting)
    note_path.write_text(
        build_obsidian_note(
            meeting,
            vault_path=vault_path,
            transcript_link_path=copied.get("transcript"),
            summary_link_path=copied.get("summary"),
            media_link_path=media_copy,
        ),
        encoding="utf-8",
    )
    return note_path
