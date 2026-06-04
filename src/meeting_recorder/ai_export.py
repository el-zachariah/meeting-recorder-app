from __future__ import annotations

from pathlib import Path

from .organizer import MeetingFolder, read_meeting_metadata

TARGET_NAMES = {
    "claude": "Claude",
    "claude-code": "Claude Code",
    "codex": "Codex",
    "chatgpt": "ChatGPT",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def build_ai_prompt(meeting: MeetingFolder, target: str = "claude") -> str:
    name = TARGET_NAMES.get(target, target.replace("-", " ").title())
    metadata = read_meeting_metadata(meeting)
    title = str(metadata.get("title") or meeting.path.name[20:] or meeting.path.name)
    transcript = _read(meeting.transcript_path)
    summary = _read(meeting.summary_path)
    return f"""# Prompt for {name}

You are helping refine meeting notes from local transcript text exported by Meeting Recorder.

Privacy context:
- The recording stayed local in Meeting Recorder.
- This prompt includes transcript text only because the user chose to paste/export it.
- Do not claim access to audio/video, screen contents, or files that are not included below.

Task:
Create a high-quality meeting summary with these sections:
1. Executive summary
2. Key decisions
3. Action items with owners if inferable
4. Open questions
5. Important details worth preserving
6. Cleaned transcript notes if useful

Meeting title: {title}
Created: {metadata.get('created_at') or 'unknown'}
Started: {metadata.get('started_at') or 'unknown'}
Ended: {metadata.get('ended_at') or 'unknown'}

Existing local summary, if any:

```markdown
{summary or 'No existing summary.'}
```

Local transcript text:

```text
{transcript or 'No transcript text available yet.'}
```
"""


def export_ai_prompt(meeting: MeetingFolder, target: str = "claude") -> Path:
    safe_target = target.lower().replace(" ", "-")
    path = meeting.path / f"prompt-for-{safe_target}.md"
    path.write_text(build_ai_prompt(meeting, target=target), encoding="utf-8")
    return path
