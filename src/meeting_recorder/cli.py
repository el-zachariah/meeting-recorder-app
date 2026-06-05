from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile

from .ai_export import export_ai_prompt
from .library import describe_meeting, open_path, resolve_meeting_path, scan_meetings
from .obsidian import export_meeting_to_obsidian
from .organizer import MeetingFolder, organize_recording
from .recorder import start_recording, stop_recording
from .status import build_environment_report, format_report_text
from .summarizer import SummaryConfigurationError, summarize_transcript
from .transcription import engine_status, transcribe

DEFAULT_DIR = Path.home() / "Meetings"


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _has_transcription_engine() -> bool:
    status = engine_status()
    return any(bool(value) for key, value in status.items() if key != "ffmpeg")


def cmd_record(args: argparse.Namespace) -> int:
    wants_transcript = not args.no_transcribe
    if wants_transcript and not args.record_without_transcriber and not _has_transcription_engine():
        msg = (
            "No local Whisper-compatible transcriber is installed. Install faster-whisper, whisper.cpp/whisper-cli, or OpenAI Whisper CLI; "
            "or rerun with --record-without-transcriber / --no-transcribe to save recording only."
        )
        if args.json:
            _print_json({"ok": False, "error": msg, "missing": "transcriber"})
        else:
            print(msg, file=sys.stderr)
        return 2
    if args.record_without_transcriber:
        args.no_transcribe = True
        args.no_summary = True
    if not args.video and args.no_system_audio and args.no_mic:
        msg = "No recordable input selected. Enable system audio, enable microphone, or pass --video for screen-only capture."
        if args.json:
            _print_json({"ok": False, "error": msg, "missing": "input"})
        else:
            print(msg, file=sys.stderr)
        return 2
    raw_dir = Path(args.raw_dir).expanduser() if args.raw_dir else Path(tempfile.mkdtemp(prefix="meeting-recorder-raw-"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(raw_dir, 0o700)
    raw_file = raw_dir / f"recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{'mkv' if args.video else 'mka'}"
    if not args.json:
        mode = "screen + audio" if args.video else "audio-first"
        print(f"Starting {mode} recording. Press Enter to stop.")
    try:
        recorder = start_recording(
            raw_file,
            fps=args.fps,
            size=args.size,
            display=args.display,
            include_system_audio=not args.no_system_audio,
            include_mic=not args.no_mic,
            include_video=bool(args.video),
        )
    except RuntimeError as exc:
        if args.json:
            _print_json({"ok": False, "error": str(exc)})
        else:
            print(f"Recording could not start: {exc}", file=sys.stderr)
        return 2
    try:
        input()
    except KeyboardInterrupt:
        pass
    if not args.json:
        print("Stopping...")
    stop_recording(recorder)
    if not raw_file.exists() or raw_file.stat().st_size == 0:
        msg = "Recording failed or no output was produced. Check DISPLAY, screen size, and ffmpeg audio/video permissions."
        if recorder.stderr_log:
            msg += f" ffmpeg log: {recorder.stderr_log}"
        if args.json:
            _print_json({"ok": False, "error": msg, "ffmpeg_log": str(recorder.stderr_log) if recorder.stderr_log else None})
        else:
            print(msg, file=sys.stderr)
        return 2
    meeting = organize_recording(raw_file, Path(args.output_dir), args.title, metadata={"capture": "ffmpeg local capture; command details intentionally omitted from metadata"})
    try:
        raw_dir.rmdir()
    except OSError:
        pass
    if not args.json:
        print(f"Organized recording: {meeting.media_path}")
    if not args.no_transcribe:
        if not args.json:
            print("Transcribing locally if an engine is available...")
        transcribe(meeting.media_path, meeting.transcript_path, model=args.model)  # type: ignore[arg-type]
        if not args.json:
            print(f"Transcript: {meeting.transcript_path}")
        if not args.no_summary:
            summarize_transcript(meeting.transcript_path, meeting.summary_path)
            if not args.json:
                print(f"Summary: {meeting.summary_path}")
    if args.open:
        open_path(meeting.path)
    if args.json:
        _print_json({"ok": True, "meeting_path": str(meeting.path), "media_path": str(meeting.media_path), "transcript_path": str(meeting.transcript_path), "summary_path": str(meeting.summary_path), "ffmpeg_log": str(recorder.stderr_log) if recorder.stderr_log else None})
    return 0


def cmd_organize(args: argparse.Namespace) -> int:
    meeting = organize_recording(Path(args.media), Path(args.output_dir), args.title)
    print(meeting.path)
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    media = Path(args.media).expanduser().resolve()
    out = Path(args.output).expanduser().resolve() if args.output else media.parent / "transcript.txt"
    text = transcribe(media, out, model=args.model)
    print(f"Wrote {out}")
    if text.startswith("# Transcript unavailable"):
        print("No local transcription engine found; wrote instructions instead.")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    transcript = Path(args.transcript).expanduser().resolve()
    out = Path(args.output).expanduser().resolve() if args.output else transcript.parent / "summary.md"
    try:
        summarize_transcript(transcript, out, use_api=args.use_api)
    except SummaryConfigurationError as exc:
        print(f"Summary configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {out}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = build_environment_report(Path(args.output_dir))
    if getattr(args, "check", None):
        report = report.filtered(args.check)
    if args.json:
        _print_json(report.to_dict())
    else:
        print(format_report_text(report), end="")
    return 0 if report.ok else 1


def cmd_list(args: argparse.Namespace) -> int:
    items = scan_meetings(Path(args.output_dir), limit=args.limit)
    if args.json:
        _print_json([item.to_dict() for item in items])
    else:
        if not items:
            print("No meetings found.")
            return 0
        for item in items:
            created = item.created_at or "unknown date"
            media = "media" if item.media_path else "no-media"
            transcript = "transcript" if item.transcript_path else "no-transcript"
            summary = "summary" if item.summary_path else "no-summary"
            print(f"{item.id}\t{created}\t{item.title}\t{media},{transcript},{summary}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    item = describe_meeting(Path(args.output_dir), args.meeting)
    if args.json:
        _print_json(item.to_dict())
    else:
        print(f"Title: {item.title}")
        print(f"ID: {item.id}")
        print(f"Created: {item.created_at or 'unknown'}")
        print(f"Folder: {item.path}")
        print(f"Media: {item.media_path or 'missing'}")
        print(f"Transcript: {item.transcript_path or 'missing'}")
        print(f"Summary: {item.summary_path or 'missing'}")
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    item_path = resolve_meeting_path(Path(args.output_dir), args.meeting)
    target = item_path
    if args.target != "folder":
        item = describe_meeting(Path(args.output_dir), item_path)
        target = {
            "media": item.media_path,
            "transcript": item.transcript_path,
            "summary": item.summary_path,
        }[args.target]
        if target is None:
            print(f"Meeting has no {args.target} artifact yet", file=sys.stderr)
            return 2
    open_path(target)
    print(target)
    return 0


def _meeting_folder_from_item(item) -> MeetingFolder:
    media_path = item.media_path
    return MeetingFolder(item.path, media_path, item.path / "transcript.txt", item.path / "summary.md", item.path / "metadata.json")


def cmd_export_obsidian(args: argparse.Namespace) -> int:
    item = describe_meeting(Path(args.output_dir), args.meeting)
    note_path = export_meeting_to_obsidian(
        _meeting_folder_from_item(item),
        Path(args.vault),
        folder=args.folder,
        copy_media=args.copy_media,
        copy_text_artifacts=args.copy_text_artifacts,
    )
    print(note_path)
    return 0


def cmd_export_ai_prompt(args: argparse.Namespace) -> int:
    item = describe_meeting(Path(args.output_dir), args.meeting)
    prompt_path = export_ai_prompt(_meeting_folder_from_item(item), target=args.target)
    print(prompt_path)
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from .gui import main as gui_main
    gui_main(default_dir=Path(args.output_dir))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first Linux meeting recorder")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("record", help="Record audio-first meeting audio, optionally with screen video, then organize/transcribe/summarize")
    p.add_argument("--title", default="meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--raw-dir", default=None, help="Private temporary raw recording directory. Defaults to a new 0700 temp dir per recording.")
    p.add_argument("--fps", type=int, default=15, help="Video frame rate when --video is enabled")
    p.add_argument("--video", action="store_true", help="Also record screen video. Off by default so meeting/system audio is the priority.")
    p.add_argument("--size", default=None, help="Screen capture size for --video, e.g. 1920x1080. Defaults to auto-detection or MEETING_RECORDER_SIZE")
    p.add_argument("--display", default=None, help="X11 display to capture, e.g. :0.0. Defaults to DISPLAY")
    p.add_argument("--no-system-audio", action="store_true")
    p.add_argument("--no-mic", action="store_true")
    p.add_argument("--no-transcribe", action="store_true")
    p.add_argument("--record-without-transcriber", action="store_true", help="Explicitly save recording only when no local Whisper-compatible transcriber is installed")
    p.add_argument("--no-summary", action="store_true", help="Skip summary generation after transcription")
    p.add_argument("--open", action="store_true", help="Open the meeting folder after recording")
    p.add_argument("--json", action="store_true", help="Print machine-readable result")
    p.add_argument("--model", default="base")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("organize", help="Move a media file into a timestamped meeting folder")
    p.add_argument("--media", required=True)
    p.add_argument("--title", default="meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.set_defaults(func=cmd_organize)

    p = sub.add_parser("transcribe", help="Transcribe a media file with local Whisper-compatible engine if installed")
    p.add_argument("--media", required=True)
    p.add_argument("--output")
    p.add_argument("--model", default="base")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("summarize", help="Generate a local extractive summary from transcript.txt")
    p.add_argument("--transcript", required=True)
    p.add_argument("--output")
    p.add_argument("--use-api", action="store_true", help="Opt-in OpenAI-compatible API only if OPENAI_BASE_URL and OPENAI_API_KEY are set")
    p.set_defaults(func=cmd_summarize)

    for name in ("doctor", "status"):
        p = sub.add_parser(name, help="Show actionable recording/transcription environment checks")
        p.add_argument("--output-dir", default=str(DEFAULT_DIR))
        p.add_argument("--json", action="store_true")
        p.add_argument("--check", action="append", help="Only show a named check; may be repeated")
        p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("list", help="List saved meetings")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="Show details for one meeting")
    p.add_argument("meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("open", help="Open a meeting folder or artifact")
    p.add_argument("meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--target", choices=["folder", "media", "transcript", "summary"], default="folder")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("export-obsidian", help="Export a meeting note into an Obsidian vault")
    p.add_argument("meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--vault", required=True, help="Path to your Obsidian vault")
    p.add_argument("--folder", default="Meetings", help="Folder inside the vault for notes")
    p.add_argument("--copy-media", action="store_true", help="Copy recording media into the vault (off by default to avoid sync bloat)")
    p.add_argument("--copy-text-artifacts", action="store_true", help="Copy transcript/summary into vault assets and link to those copies")
    p.set_defaults(func=cmd_export_obsidian)

    p = sub.add_parser("export-ai-prompt", help="Write a local Claude/Codex-ready prompt from a meeting transcript")
    p.add_argument("meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--target", choices=["claude", "claude-code", "codex", "chatgpt"], default="claude")
    p.set_defaults(func=cmd_export_ai_prompt)

    p = sub.add_parser("gui", help="Launch the tray-style dropdown recorder")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.set_defaults(func=cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
