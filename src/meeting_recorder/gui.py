from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from .library import MeetingListItem, open_path, scan_meetings
from .organizer import MeetingFolder, organize_recording
from .recorder import RecorderProcess, start_recording, stop_recording
from .status import CheckItem, build_environment_report
from .summarizer import summarize_transcript
from .transcription import transcribe


@dataclass(frozen=True)
class RecentMeetingRow:
    id: str
    title: str
    created: str
    has_transcript: bool
    has_summary: bool
    path: Path


def format_duration(seconds: float | int) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_check_item(check: CheckItem) -> str:
    labels = {"pass": "✓", "warn": "!", "error": "×"}
    return f"{labels.get(check.status, '?')} {check.name}: {check.message}"


def progress_message(stage: str) -> str:
    messages = {
        "ready": "Ready to record locally.",
        "recording": "Recording in progress…",
        "stopping": "Stopping recorder…",
        "organizing": "Saving meeting folder…",
        "transcribing": "Creating transcript or setup report…",
        "summarizing": "Creating summary…",
        "complete": "Recording complete.",
        "error": "Needs attention.",
    }
    return messages.get(stage, stage)


def recent_meeting_rows(items: list[MeetingListItem]) -> list[RecentMeetingRow]:
    return [
        RecentMeetingRow(
            id=item.id,
            title=item.title,
            created=item.created_at or "unknown date",
            has_transcript=item.transcript_path is not None,
            has_summary=item.summary_path is not None,
            path=item.path,
        )
        for item in items
    ]


class MeetingRecorderGUI:
    def __init__(self, root: tk.Tk, default_dir: Path):
        self.root = root
        self.root.title("Meeting Recorder")
        self.root.minsize(820, 640)
        self.default_dir = Path(default_dir).expanduser()
        self.recorder: RecorderProcess | None = None
        self.raw_file: Path | None = None
        self.recording_started_at: float | None = None
        self.current_meeting: MeetingFolder | None = None

        self.title_var = tk.StringVar(value="meeting")
        self.dir_var = tk.StringVar(value=str(self.default_dir))
        self.fps_var = tk.IntVar(value=15)
        self.size_var = tk.StringVar(value="")
        self.system_audio_var = tk.BooleanVar(value=True)
        self.mic_var = tk.BooleanVar(value=True)
        self.transcribe_var = tk.BooleanVar(value=True)
        self.summary_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value=progress_message("ready"))
        self.elapsed_var = tk.StringVar(value="00:00")

        self._build_styles()
        self._build_layout()
        self.refresh_dashboard()
        self.refresh_recent()

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Section.TLabelframe.Label", font=("TkDefaultFont", 11, "bold"))
        style.configure("Privacy.TLabel", foreground="#0b6b3a")
        style.configure("Error.TLabel", foreground="#9b1c1c")
        style.configure("Warn.TLabel", foreground="#8a5a00")
        style.configure("Pass.TLabel", foreground="#0b6b3a")

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=14)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(3, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Meeting Recorder", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Local-first: no uploads unless you explicitly opt in.", style="Privacy.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="Refresh setup", command=self.refresh_dashboard).grid(row=0, column=1, rowspan=2, sticky="e")

        setup = ttk.Labelframe(main, text="Setup checklist", style="Section.TLabelframe", padding=10)
        setup.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        setup.columnconfigure(0, weight=1)
        self.checks_frame = ttk.Frame(setup)
        self.checks_frame.grid(row=0, column=0, sticky="ew")

        options = ttk.Labelframe(main, text="Capture options", style="Section.TLabelframe", padding=10)
        options.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="Title").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(options, textvariable=self.title_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=3)
        ttk.Label(options, text="Output").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(options, textvariable=self.dir_var).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Button(options, text="Browse…", command=self.browse).grid(row=1, column=2, padx=(6, 0), pady=3)
        ttk.Label(options, text="FPS").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Spinbox(options, from_=1, to=60, textvariable=self.fps_var, width=8).grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(options, text="Size").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(options, textvariable=self.size_var).grid(row=3, column=1, sticky="ew", pady=3)
        ttk.Label(options, text="blank = auto").grid(row=3, column=2, sticky="w", padx=(6, 0), pady=3)
        ttk.Checkbutton(options, text="System audio", variable=self.system_audio_var).grid(row=4, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Checkbutton(options, text="Microphone", variable=self.mic_var).grid(row=5, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Checkbutton(options, text="Transcribe after recording", variable=self.transcribe_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Checkbutton(options, text="Summarize after transcription", variable=self.summary_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=3)

        controls = ttk.Labelframe(main, text="Recording controls", style="Section.TLabelframe", padding=10)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=12)
        controls.columnconfigure(4, weight=1)
        self.start_button = ttk.Button(controls, text="Start recording", command=self.start)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = ttk.Button(controls, text="Stop + organize", command=self.stop, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 16))
        ttk.Label(controls, text="Elapsed:").grid(row=0, column=2, sticky="e")
        ttk.Label(controls, textvariable=self.elapsed_var, font=("TkDefaultFont", 14, "bold")).grid(row=0, column=3, sticky="w", padx=(6, 16))
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=4, sticky="w")

        recent = ttk.Labelframe(main, text="Recent meetings", style="Section.TLabelframe", padding=10)
        recent.grid(row=3, column=0, sticky="nsew", padx=(0, 8))
        recent.columnconfigure(0, weight=1)
        recent.rowconfigure(0, weight=1)
        self.recent_frame = ttk.Frame(recent)
        self.recent_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Button(recent, text="Refresh meetings", command=self.refresh_recent).grid(row=1, column=0, sticky="w", pady=(8, 0))

        actions = ttk.Labelframe(main, text="Completion actions", style="Section.TLabelframe", padding=10)
        actions.grid(row=3, column=1, sticky="nsew", padx=(8, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, text="Open the newest completed artifacts.", wraplength=330).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.open_folder_button = ttk.Button(actions, text="Open folder", command=lambda: self._open_current("folder"), state="disabled")
        self.open_folder_button.grid(row=1, column=0, sticky="ew", pady=3)
        self.open_transcript_button = ttk.Button(actions, text="Open transcript", command=lambda: self._open_current("transcript"), state="disabled")
        self.open_transcript_button.grid(row=2, column=0, sticky="ew", pady=3)
        self.open_summary_button = ttk.Button(actions, text="Open summary", command=lambda: self._open_current("summary"), state="disabled")
        self.open_summary_button.grid(row=3, column=0, sticky="ew", pady=3)

    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or str(self.default_dir))
        if chosen:
            self.dir_var.set(chosen)
            self.refresh_dashboard()
            self.refresh_recent()

    def refresh_dashboard(self) -> None:
        for child in self.checks_frame.winfo_children():
            child.destroy()
        try:
            report = build_environment_report(Path(self.dir_var.get()))
            checks = report.checks
        except Exception as exc:
            checks = [CheckItem("doctor", "error", f"Could not run setup checks: {exc}")]
        for row, check in enumerate(checks):
            style = {"pass": "Pass.TLabel", "warn": "Warn.TLabel", "error": "Error.TLabel"}.get(check.status, "TLabel")
            ttk.Label(self.checks_frame, text=format_check_item(check), style=style, wraplength=360, justify="left").grid(row=row, column=0, sticky="w", pady=2)

    def refresh_recent(self) -> None:
        for child in self.recent_frame.winfo_children():
            child.destroy()
        rows = recent_meeting_rows(scan_meetings(Path(self.dir_var.get()), limit=5))
        if not rows:
            ttk.Label(self.recent_frame, text="No meetings found yet.").grid(row=0, column=0, sticky="w")
            return
        for idx, row in enumerate(rows):
            artifacts = []
            if row.has_transcript:
                artifacts.append("transcript")
            if row.has_summary:
                artifacts.append("summary")
            text = f"{row.title}\n{row.created} · {', '.join(artifacts) if artifacts else 'recording only'}"
            ttk.Label(self.recent_frame, text=text, justify="left", wraplength=300).grid(row=idx, column=0, sticky="ew", pady=4)
            ttk.Button(self.recent_frame, text="Open", command=lambda path=row.path: open_path(path)).grid(row=idx, column=1, padx=(8, 0), pady=4)

    def start(self) -> None:
        try:
            raw_dir = Path(tempfile.mkdtemp(prefix="meeting-recorder-raw-"))
            raw_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(raw_dir, 0o700)
            self.raw_file = raw_dir / f"gui-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.mkv"
            size = self.size_var.get().strip() or None
            self.recorder = start_recording(
                self.raw_file,
                fps=int(self.fps_var.get()),
                size=size,
                include_system_audio=bool(self.system_audio_var.get()),
                include_mic=bool(self.mic_var.get()),
            )
        except Exception as exc:
            messagebox.showerror("Could not start recording", str(exc))
            self.status_var.set(f"Could not start: {exc}")
            return
        self.recording_started_at = time.monotonic()
        self.current_meeting = None
        self._set_completion_buttons(None)
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set(progress_message("recording"))
        self._tick_elapsed()

    def _tick_elapsed(self) -> None:
        if self.recording_started_at is None:
            return
        self.elapsed_var.set(format_duration(time.monotonic() - self.recording_started_at))
        if self.recorder and self.recorder.process.poll() is None:
            self.root.after(1000, self._tick_elapsed)

    def stop(self) -> None:
        if not self.recorder or not self.raw_file:
            return
        self.stop_button.config(state="disabled")
        self.status_var.set(progress_message("stopping"))
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stage(self, stage: str) -> None:
        self.root.after(0, lambda: self.status_var.set(progress_message(stage)))

    def _stop_worker(self) -> None:
        meeting: MeetingFolder | None = None
        try:
            self._stage("stopping")
            stop_recording(self.recorder)  # type: ignore[arg-type]
            self._stage("organizing")
            meeting = organize_recording(
                self.raw_file,
                Path(self.dir_var.get()),
                self.title_var.get(),
                metadata={"capture": "ffmpeg local capture from GUI"},
            )  # type: ignore[arg-type]
            try:
                self.raw_file.parent.rmdir()  # type: ignore[union-attr]
            except OSError:
                pass
            if self.transcribe_var.get():
                self._stage("transcribing")
                transcribe(meeting.media_path, meeting.transcript_path)  # type: ignore[arg-type]
                if self.summary_var.get():
                    self._stage("summarizing")
                    summarize_transcript(meeting.transcript_path, meeting.summary_path)
            msg = f"Done: {meeting.path}"
            stage = "complete"
        except Exception as exc:
            msg = f"Error: {exc}"
            stage = "error"
        self.root.after(0, lambda: self._finish(stage, msg, meeting))

    def _finish(self, stage: str, msg: str, meeting: MeetingFolder | None) -> None:
        self.recording_started_at = None
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set(f"{progress_message(stage)} {msg}")
        self.current_meeting = meeting
        self._set_completion_buttons(meeting)
        self.refresh_recent()

    def _set_completion_buttons(self, meeting: MeetingFolder | None) -> None:
        state = "normal" if meeting else "disabled"
        self.open_folder_button.config(state=state)
        self.open_transcript_button.config(state="normal" if meeting and meeting.transcript_path.exists() else "disabled")
        self.open_summary_button.config(state="normal" if meeting and meeting.summary_path.exists() else "disabled")

    def _open_current(self, target: str) -> None:
        if not self.current_meeting:
            return
        path = {
            "folder": self.current_meeting.path,
            "transcript": self.current_meeting.transcript_path,
            "summary": self.current_meeting.summary_path,
        }[target]
        try:
            open_path(path)
        except Exception as exc:
            messagebox.showerror("Could not open", str(exc))


def main(default_dir: Path) -> None:
    root = tk.Tk()
    MeetingRecorderGUI(root, default_dir)
    root.mainloop()
