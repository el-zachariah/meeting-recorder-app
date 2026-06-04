from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile

from .organizer import organize_recording, list_meetings
from .recorder import start_recording, stop_recording, detect_audio_inputs, build_ffmpeg_command
from .summarizer import summarize_transcript
from .transcription import transcribe, engine_status

DEFAULT_DIR = Path.home() / "Meetings"


def cmd_record(args: argparse.Namespace) -> int:
    raw_dir = Path(args.raw_dir).expanduser() if args.raw_dir else Path(tempfile.mkdtemp(prefix="meeting-recorder-raw-"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(raw_dir, 0o700)
    raw_file = raw_dir / f"recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.mkv"
    print("Starting recording. Press Enter to stop.")
    recorder = start_recording(raw_file, fps=args.fps, size=args.size, include_system_audio=not args.no_system_audio, include_mic=not args.no_mic)
    try:
        input()
    except KeyboardInterrupt:
        pass
    print("Stopping...")
    stop_recording(recorder)
    if not raw_file.exists() or raw_file.stat().st_size == 0:
        print("Recording failed or no output was produced. Check DISPLAY, screen size, and ffmpeg audio/video permissions.", file=sys.stderr)
        return 2
    meeting = organize_recording(raw_file, Path(args.output_dir), args.title, metadata={"capture": "ffmpeg local capture; command details intentionally omitted from metadata"})
    try:
        raw_dir.rmdir()
    except OSError:
        pass
    print(f"Organized recording: {meeting.media_path}")
    if not args.no_transcribe:
        print("Transcribing locally if an engine is available...")
        transcribe(meeting.media_path, meeting.transcript_path, model=args.model)  # type: ignore[arg-type]
        print(f"Transcript: {meeting.transcript_path}")
        summarize_transcript(meeting.transcript_path, meeting.summary_path)
        print(f"Summary: {meeting.summary_path}")
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
    summarize_transcript(transcript, out, use_api=args.use_api)
    print(f"Wrote {out}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print("Audio inputs:", detect_audio_inputs())
    print("Transcription engines:", engine_status())
    print("Default meetings dir:", DEFAULT_DIR)
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from .gui import main as gui_main
    gui_main(default_dir=Path(args.output_dir))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Privacy-first local meeting recorder MVP")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("record", help="Record screen + optional system audio/mic, then organize/transcribe/summarize")
    p.add_argument("--title", default="meeting")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--raw-dir", default=None, help="Private temporary raw recording directory. Defaults to a new 0700 temp dir per recording.")
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--size", default=None, help="Screen capture size, e.g. 1920x1080. Defaults to MEETING_RECORDER_SIZE or 1920x1080")
    p.add_argument("--no-system-audio", action="store_true")
    p.add_argument("--no-mic", action="store_true")
    p.add_argument("--no-transcribe", action="store_true")
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

    p = sub.add_parser("status", help="Show recording/transcription environment status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("gui", help="Launch simple Tk desktop GUI")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.set_defaults(func=cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
