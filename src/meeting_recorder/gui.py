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

from .ai_export import export_ai_prompt
from .audio_monitor import AudioLevelMonitor
from .gui_models import CaptureSelections, SetupGate, bar_geometry, compact_bar_state, popover_geometry, setup_gate_from_report
from .library import MeetingListItem, open_path, scan_meetings
from .obsidian import export_meeting_to_obsidian
from .organizer import MeetingFolder, organize_recording, rename_meeting_by_end_time, update_meeting_metadata
from .recorder import RecorderProcess, start_recording, stop_recording
from .status import CheckItem, build_environment_report
from .summarizer import summarize_transcript
from .transcription import transcribe

BG = "#08090a"
PANEL = "#0f1011"
SURFACE = "#191a1b"
SURFACE_2 = "#24262b"
TEXT = "#f7f8f8"
MUTED = "#8a8f98"
SUBTLE = "#62666d"
BORDER = "#2b2e34"
ACCENT = "#7170ff"
RECORD = "#ef4444"
SUCCESS = "#10b981"
WARN = "#f59e0b"
ERROR = "#ef4444"


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
        "ready": "Ready. Local-first recording is armed.",
        "recording": "Recording locally…",
        "stopping": "Stopping recorder…",
        "organizing": "Organizing meeting folder…",
        "transcribing": "Creating transcript or setup report…",
        "summarizing": "Creating summary…",
        "obsidian": "Exporting Obsidian note…",
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


def recording_button_text(is_recording: bool, is_busy: bool) -> str:
    if is_busy:
        return "Saving…"
    return "■ Stop" if is_recording else "● Record"


def window_geometry_for_mini(screen_width: int, screen_height: int, width: int = 360, height: int = 170) -> str:
    x = max(24, screen_width - width - 24)
    y = 24
    return f"{width}x{height}+{x}+{y}"


def stop_title_default(current_title: str) -> str:
    title = current_title.strip()
    if title:
        return title
    return f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}"


class WaveformCanvas(tk.Canvas):
    def __init__(self, master: tk.Widget, **kwargs):
        kwargs.setdefault("height", 96)
        kwargs.setdefault("bg", PANEL)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)

    def draw_levels(self, levels: list[float], recording: bool = False) -> None:
        self.delete("all")
        width = max(1, self.winfo_width() or 420)
        height = max(1, self.winfo_height() or 96)
        if not levels:
            levels = [0.0] * 48
        gap = 3
        bar_w = max(3, (width - gap * (len(levels) - 1)) / len(levels))
        mid = height / 2
        for idx, level in enumerate(levels):
            x0 = idx * (bar_w + gap)
            bar_h = max(4, level * (height - 20))
            color = RECORD if recording else ACCENT
            if level < 0.08:
                color = SUBTLE
            self.create_rectangle(x0, mid - bar_h / 2, x0 + bar_w, mid + bar_h / 2, fill=color, outline="")
        self.create_text(12, height - 12, text="live level / capture activity", fill=MUTED, anchor="w", font=("TkDefaultFont", 9))


class MeetingRecorderGUI:
    def __init__(self, root: tk.Tk, default_dir: Path, mini: bool = False):
        self.root = root
        self.mini = mini
        self.root.title("Meeting Recorder")
        self.root.configure(bg=BG)
        self.root.minsize(360 if mini else 980, 170 if mini else 720)
        self.default_dir = Path(default_dir).expanduser()
        self.recorder: RecorderProcess | None = None
        self.raw_file: Path | None = None
        self.recording_started_at: float | None = None
        self.recording_started_wall: datetime | None = None
        self.current_meeting: MeetingFolder | None = None
        self.busy = False
        self.monitor = AudioLevelMonitor(bars=36 if mini else 52)

        self.title_var = tk.StringVar(value="meeting")
        self.dir_var = tk.StringVar(value=str(self.default_dir))
        self.fps_var = tk.IntVar(value=15)
        self.size_var = tk.StringVar(value="")
        self.video_var = tk.BooleanVar(value=False)
        self.system_audio_var = tk.BooleanVar(value=True)
        self.mic_var = tk.BooleanVar(value=True)
        self.transcribe_var = tk.BooleanVar(value=True)
        self.summary_var = tk.BooleanVar(value=True)
        self.stop_time_name_var = tk.BooleanVar(value=True)
        self.obsidian_vault_var = tk.StringVar(value="")
        self.obsidian_folder_var = tk.StringVar(value="Meetings")
        self.status_var = tk.StringVar(value="Checking setup…")
        self.elapsed_var = tk.StringVar(value="00:00")
        self.privacy_var = tk.StringVar(value="LOCAL")
        self.last_report: EnvironmentReport | None = None

        self._build_styles()
        if self.mini:
            self._build_mini_layout()
            self.root.attributes("-topmost", True)
            self.root.geometry(window_geometry_for_mini(self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        else:
            self._build_layout()
            self.refresh_dashboard()
            self.refresh_recent()
        self._tick_waveform()
        self.refresh_setup_state()

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("TkDefaultFont", 22, "bold"))
        style.configure("Hero.TLabel", background=PANEL, foreground=TEXT, font=("TkDefaultFont", 28, "bold"))
        style.configure("Timer.TLabel", background=PANEL, foreground=TEXT, font=("TkDefaultFont", 30, "bold"))
        style.configure("Privacy.TLabel", background=BG, foreground=SUCCESS)
        style.configure("Error.TLabel", background=PANEL, foreground=ERROR)
        style.configure("Warn.TLabel", background=PANEL, foreground=WARN)
        style.configure("Pass.TLabel", background=PANEL, foreground=SUCCESS)
        style.configure("TButton", background=SURFACE_2, foreground=TEXT, bordercolor=BORDER, focusthickness=0, padding=(10, 7))
        style.map("TButton", background=[("active", "#30323a")])
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER)
        style.configure("TSpinbox", fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER)
        style.configure("Section.TLabelframe", background=PANEL, foreground=TEXT, bordercolor=BORDER)
        style.configure("Section.TLabelframe.Label", background=PANEL, foreground=TEXT, font=("TkDefaultFont", 11, "bold"))

    def _card(self, parent: tk.Widget, row: int, column: int, **grid) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        frame.grid(row=row, column=column, sticky="nsew", **grid)
        return frame

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=18)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Meeting Recorder", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Local-first screen + audio capture with Obsidian-ready notes.", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.privacy_badge = tk.Label(header, textvariable=self.privacy_var, bg="#11251c", fg=SUCCESS, padx=12, pady=5, font=("TkDefaultFont", 10, "bold"))
        self.privacy_badge.grid(row=0, column=1, sticky="e")
        ttk.Button(header, text="Refresh setup", command=self.refresh_dashboard).grid(row=1, column=1, sticky="e", pady=(4, 0))

        recorder = self._card(main, 1, 0, padx=(0, 10))
        recorder.columnconfigure(0, weight=1)
        ttk.Label(recorder, text="Ready when you are", style="Hero.TLabel").grid(row=0, column=0, pady=(0, 8))
        self.record_button = tk.Button(
            recorder,
            text=recording_button_text(False, False),
            command=self.toggle_recording,
            bg="#15171c",
            fg=TEXT,
            activebackground="#261719",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=36,
            pady=26,
            font=("TkDefaultFont", 24, "bold"),
            cursor="hand2",
        )
        self.record_button.grid(row=1, column=0, pady=8)
        ttk.Label(recorder, textvariable=self.elapsed_var, style="Timer.TLabel").grid(row=2, column=0, pady=(0, 8))
        self.waveform = WaveformCanvas(recorder)
        self.waveform.grid(row=3, column=0, sticky="ew", pady=(8, 10))
        ttk.Label(recorder, textvariable=self.status_var, style="PanelMuted.TLabel", wraplength=520, justify="center").grid(row=4, column=0, sticky="ew")

        options = ttk.Labelframe(main, text="Capture options", style="Section.TLabelframe", padding=12)
        options.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        options.columnconfigure(1, weight=1)
        self._build_options(options)

        lower = ttk.Frame(main)
        lower.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)
        lower.columnconfigure(2, weight=1)
        lower.rowconfigure(0, weight=1)

        setup = ttk.Labelframe(lower, text="Setup checklist", style="Section.TLabelframe", padding=10)
        setup.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        setup.columnconfigure(0, weight=1)
        self.checks_frame = ttk.Frame(setup, style="Panel.TFrame")
        self.checks_frame.grid(row=0, column=0, sticky="ew")

        recent = ttk.Labelframe(lower, text="Recent meetings", style="Section.TLabelframe", padding=10)
        recent.grid(row=0, column=1, sticky="nsew", padx=8)
        recent.columnconfigure(0, weight=1)
        self.recent_frame = ttk.Frame(recent, style="Panel.TFrame")
        self.recent_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Button(recent, text="Refresh", command=self.refresh_recent).grid(row=1, column=0, sticky="w", pady=(8, 0))

        actions = ttk.Labelframe(lower, text="Notes + exports", style="Section.TLabelframe", padding=10)
        actions.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        actions.columnconfigure(0, weight=1)
        self._build_actions(actions)

    def _build_options(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Meeting title", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.title_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(parent, text="Output folder", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.dir_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Browse…", command=self.browse).grid(row=1, column=2, padx=(6, 0), pady=4)
        ttk.Label(parent, text="FPS", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(parent, from_=1, to=60, textvariable=self.fps_var, width=8).grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(parent, text="Size", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.size_var).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(parent, text="blank = auto", style="PanelMuted.TLabel").grid(row=3, column=2, sticky="w", padx=(6, 0), pady=4)
        ttk.Checkbutton(parent, text="Record screen video (optional)", variable=self.video_var, command=self.refresh_setup_state).grid(row=4, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(parent, text="System audio (meeting/app sound)", variable=self.system_audio_var, command=self.refresh_setup_state).grid(row=5, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(parent, text="Microphone", variable=self.mic_var, command=self.refresh_setup_state).grid(row=6, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(parent, text="Transcribe after recording", variable=self.transcribe_var, command=self.refresh_setup_state).grid(row=7, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(parent, text="Summarize after transcription", variable=self.summary_var, command=self.refresh_setup_state).grid(row=8, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(parent, text="Name saved folder by stop time", variable=self.stop_time_name_var).grid(row=9, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Label(parent, text="Obsidian vault", style="Panel.TLabel").grid(row=10, column=0, sticky="w", pady=(12, 4))
        ttk.Entry(parent, textvariable=self.obsidian_vault_var).grid(row=10, column=1, sticky="ew", pady=(12, 4))
        ttk.Button(parent, text="Vault…", command=self.browse_obsidian).grid(row=10, column=2, padx=(6, 0), pady=(12, 4))
        ttk.Label(parent, text="Vault folder", style="Panel.TLabel").grid(row=11, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.obsidian_folder_var).grid(row=11, column=1, columnspan=2, sticky="ew", pady=4)

    def _build_actions(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Post-meeting workflows stay local unless you explicitly paste or enable an API elsewhere.", style="PanelMuted.TLabel", wraplength=280).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.open_folder_button = ttk.Button(parent, text="Open folder", command=lambda: self._open_current("folder"), state="disabled")
        self.open_folder_button.grid(row=1, column=0, sticky="ew", pady=3)
        self.open_transcript_button = ttk.Button(parent, text="Open transcript", command=lambda: self._open_current("transcript"), state="disabled")
        self.open_transcript_button.grid(row=2, column=0, sticky="ew", pady=3)
        self.open_summary_button = ttk.Button(parent, text="Open summary", command=lambda: self._open_current("summary"), state="disabled")
        self.open_summary_button.grid(row=3, column=0, sticky="ew", pady=3)
        self.obsidian_button = ttk.Button(parent, text="Export to Obsidian", command=self.export_obsidian_current, state="disabled")
        self.obsidian_button.grid(row=4, column=0, sticky="ew", pady=(12, 3))
        self.ai_prompt_button = ttk.Button(parent, text="Create Claude/Codex prompt", command=self.export_ai_prompt_current, state="disabled")
        self.ai_prompt_button.grid(row=5, column=0, sticky="ew", pady=3)
        self.open_note_button = ttk.Button(parent, text="Open Obsidian note", command=lambda: self._open_optional_path(getattr(self, "last_obsidian_note", None)), state="disabled")
        self.open_note_button.grid(row=6, column=0, sticky="ew", pady=3)

    def _build_mini_layout(self) -> None:
        main = ttk.Frame(self.root, padding=12, style="Panel.TFrame")
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        self.record_button = tk.Button(main, text=recording_button_text(False, False), command=self.toggle_recording, bg="#15171c", fg=TEXT, activebackground="#261719", activeforeground=TEXT, relief="flat", bd=0, padx=18, pady=14, font=("TkDefaultFont", 16, "bold"), cursor="hand2")
        self.record_button.grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="nsew")
        ttk.Label(main, text="Meeting Recorder", style="Panel.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(main, textvariable=self.elapsed_var, style="Panel.TLabel", font=("TkDefaultFont", 18, "bold")).grid(row=1, column=1, sticky="w")
        self.waveform = WaveformCanvas(main, height=52)
        self.waveform.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        ttk.Label(main, textvariable=self.status_var, style="PanelMuted.TLabel", wraplength=320).grid(row=3, column=0, columnspan=2, sticky="ew")

    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or str(self.default_dir))
        if chosen:
            self.dir_var.set(chosen)
            if not self.mini:
                self.refresh_dashboard()
                self.refresh_recent()

    def browse_obsidian(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.obsidian_vault_var.get() or str(Path.home()))
        if chosen:
            self.obsidian_vault_var.set(chosen)

    def refresh_setup_state(self) -> SetupGate | None:
        try:
            report = build_environment_report(Path(self.dir_var.get()))
            self.last_report = report
            gate = setup_gate_from_report(
                report,
                CaptureSelections(
                    include_system_audio=bool(self.system_audio_var.get()),
                    include_mic=bool(self.mic_var.get()),
                    include_video=bool(self.video_var.get()),
                    transcribe=bool(self.transcribe_var.get()),
                    summarize=bool(self.summary_var.get()),
                ),
            )
        except Exception as exc:
            self.status_var.set(f"Setup check failed: {exc}")
            return None
        self.status_var.set(gate.message if gate.status != "ready" else progress_message("ready"))
        return gate

    def refresh_dashboard(self) -> None:
        if self.mini:
            return
        for child in self.checks_frame.winfo_children():
            child.destroy()
        try:
            report = build_environment_report(Path(self.dir_var.get()))
            checks = report.checks
        except Exception as exc:
            checks = [CheckItem("doctor", "error", f"Could not run setup checks: {exc}")]
        for row, check in enumerate(checks):
            style = {"pass": "Pass.TLabel", "warn": "Warn.TLabel", "error": "Error.TLabel"}.get(check.status, "Panel.TLabel")
            ttk.Label(self.checks_frame, text=format_check_item(check), style=style, wraplength=310, justify="left").grid(row=row, column=0, sticky="w", pady=2)

    def refresh_recent(self) -> None:
        if self.mini:
            return
        for child in self.recent_frame.winfo_children():
            child.destroy()
        rows = recent_meeting_rows(scan_meetings(Path(self.dir_var.get()), limit=5))
        if not rows:
            ttk.Label(self.recent_frame, text="No meetings found yet.", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w")
            return
        for idx, row in enumerate(rows):
            artifacts = []
            if row.has_transcript:
                artifacts.append("transcript")
            if row.has_summary:
                artifacts.append("summary")
            text = f"{row.title}\n{row.created} · {', '.join(artifacts) if artifacts else 'recording only'}"
            ttk.Label(self.recent_frame, text=text, justify="left", wraplength=260, style="Panel.TLabel").grid(row=idx, column=0, sticky="ew", pady=4)
            ttk.Button(self.recent_frame, text="Open", command=lambda path=row.path: open_path(path)).grid(row=idx, column=1, padx=(8, 0), pady=4)

    def toggle_recording(self) -> None:
        if self.busy:
            return
        if self.recorder and self.recorder.process.poll() is None:
            self.stop()
        else:
            self.start()

    def _update_record_button(self) -> None:
        is_recording = bool(self.recorder and self.recorder.process.poll() is None)
        self.record_button.config(text=recording_button_text(is_recording, self.busy), bg=RECORD if is_recording else "#15171c")

    def start(self) -> None:
        gate = self.refresh_setup_state()
        if gate and not gate.can_start_selected_config:
            if gate.suggested_action == "Record without system audio":
                if messagebox.askyesno("System audio is not ready", f"{gate.message}\n\nRecord without system audio instead?"):
                    self.system_audio_var.set(False)
                    gate = self.refresh_setup_state()
                else:
                    return
            elif gate.suggested_action == "Record without transcript":
                if messagebox.askyesno("Local transcriber is not installed", f"{gate.message}\n\nRecord without transcript for now?"):
                    self.transcribe_var.set(False)
                    self.summary_var.set(False)
                    gate = self.refresh_setup_state()
                else:
                    return
            else:
                messagebox.showwarning("Setup needed", "\n".join(gate.blocking or gate.warnings or [gate.message]))
                return
        try:
            raw_dir = Path(tempfile.mkdtemp(prefix="meeting-recorder-raw-"))
            raw_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(raw_dir, 0o700)
            ext = "mkv" if self.video_var.get() else "mka"
            self.raw_file = raw_dir / f"gui-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"
            size = self.size_var.get().strip() or None
            self.recorder = start_recording(
                self.raw_file,
                fps=int(self.fps_var.get()),
                size=size,
                include_system_audio=bool(self.system_audio_var.get()),
                include_mic=bool(self.mic_var.get()),
                include_video=bool(self.video_var.get()),
            )
        except Exception as exc:
            messagebox.showerror("Could not start recording", str(exc))
            self.status_var.set(f"Could not start: {exc}")
            return
        self.recording_started_at = time.monotonic()
        self.recording_started_wall = datetime.now()
        self.current_meeting = None
        self._set_completion_buttons(None)
        self.status_var.set(progress_message("recording"))
        self.monitor.start()
        self._update_record_button()
        self._tick_elapsed()

    def _tick_elapsed(self) -> None:
        if self.recording_started_at is None:
            return
        self.elapsed_var.set(format_duration(time.monotonic() - self.recording_started_at))
        if self.recorder and self.recorder.process.poll() is None:
            self.root.after(1000, self._tick_elapsed)

    def _tick_waveform(self) -> None:
        is_recording = bool(self.recorder and self.recorder.process.poll() is None)
        levels = self.monitor.tick()
        self.waveform.draw_levels(levels, recording=is_recording)
        self.root.after(120 if is_recording else 350, self._tick_waveform)

    def stop(self) -> None:
        if not self.recorder or not self.raw_file:
            return
        title = stop_title_default(self.title_var.get())
        self.title_var.set(title.strip() or stop_title_default(""))
        self.busy = True
        self.monitor.stop()
        self.status_var.set(progress_message("stopping"))
        self._update_record_button()
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stage(self, stage: str) -> None:
        self.root.after(0, lambda: self.status_var.set(progress_message(stage)))

    def _stop_worker(self) -> None:
        meeting: MeetingFolder | None = None
        ended = datetime.now()
        duration = int(time.monotonic() - self.recording_started_at) if self.recording_started_at else None
        try:
            self._stage("stopping")
            stop_recording(self.recorder)  # type: ignore[arg-type]
            if not self.raw_file or not self.raw_file.exists() or self.raw_file.stat().st_size == 0:
                log_path = self.recorder.stderr_log if self.recorder else None
                log_note = f" ffmpeg log: {log_path}" if log_path else ""
                raise RuntimeError(f"Recording failed or no output was produced.{log_note}")
            self._stage("organizing")
            meeting = organize_recording(
                self.raw_file,
                Path(self.dir_var.get()),
                self.title_var.get(),
                metadata={
                    "capture": "ffmpeg local capture from GUI",
                    "started_at": self.recording_started_wall.isoformat(timespec="seconds") if self.recording_started_wall else None,
                    "ended_at": ended.isoformat(timespec="seconds"),
                    "duration_seconds": duration,
                },
            )  # type: ignore[arg-type]
            if self.stop_time_name_var.get():
                meeting = rename_meeting_by_end_time(meeting, self.title_var.get(), ended)
                update_meeting_metadata(meeting, {"duration_seconds": duration})
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
            msg = f"Saved: {meeting.path}"
            stage = "complete"
        except Exception as exc:
            msg = f"Error: {exc}"
            stage = "error"
        self.root.after(0, lambda: self._finish(stage, msg, meeting))

    def _finish(self, stage: str, msg: str, meeting: MeetingFolder | None) -> None:
        self.recording_started_at = None
        self.recording_started_wall = None
        self.busy = False
        self.status_var.set(f"{progress_message(stage)} {msg}")
        self.current_meeting = meeting
        self._set_completion_buttons(meeting)
        self._update_record_button()
        if not self.mini:
            self.refresh_recent()

    def _set_completion_buttons(self, meeting: MeetingFolder | None) -> None:
        if self.mini:
            return
        state = "normal" if meeting else "disabled"
        self.open_folder_button.config(state=state)
        self.open_transcript_button.config(state="normal" if meeting and meeting.transcript_path.exists() else "disabled")
        self.open_summary_button.config(state="normal" if meeting and meeting.summary_path.exists() else "disabled")
        self.obsidian_button.config(state=state)
        self.ai_prompt_button.config(state=state)

    def _open_current(self, target: str) -> None:
        if not self.current_meeting:
            return
        path = {
            "folder": self.current_meeting.path,
            "transcript": self.current_meeting.transcript_path,
            "summary": self.current_meeting.summary_path,
        }[target]
        self._open_optional_path(path)

    def _open_optional_path(self, path: Path | None) -> None:
        if not path:
            return
        try:
            open_path(path)
        except Exception as exc:
            messagebox.showerror("Could not open", str(exc))

    def export_obsidian_current(self) -> None:
        if not self.current_meeting:
            return
        vault = self.obsidian_vault_var.get().strip()
        if not vault:
            messagebox.showinfo("Choose an Obsidian vault", "Pick your Obsidian vault folder first.")
            self.browse_obsidian()
            vault = self.obsidian_vault_var.get().strip()
            if not vault:
                return
        try:
            self._stage("obsidian")
            note = export_meeting_to_obsidian(self.current_meeting, Path(vault), folder=self.obsidian_folder_var.get().strip() or "Meetings")
            self.last_obsidian_note = note
            self.open_note_button.config(state="normal")
            self.status_var.set(f"Obsidian note exported: {note}")
        except Exception as exc:
            messagebox.showerror("Could not export Obsidian note", str(exc))
            self.status_var.set(f"Obsidian export failed: {exc}")

    def export_ai_prompt_current(self) -> None:
        if not self.current_meeting:
            return
        try:
            prompt = export_ai_prompt(self.current_meeting, target="claude-code")
            self.status_var.set(f"Claude/Codex prompt written: {prompt}")
            open_path(prompt)
        except Exception as exc:
            messagebox.showerror("Could not create prompt", str(exc))
            self.status_var.set(f"AI prompt export failed: {exc}")


class CompactDropdownGUI(MeetingRecorderGUI):
    """Compact notification-bar-style recorder with dropdown controls.

    This intentionally stays dependency-free (Tk only) because Linux native tray APIs are fragmented.
    It gives the user the requested top-corner/dropdown workflow as the only desktop surface.
    """

    def __init__(self, root: tk.Tk, default_dir: Path):
        super().__init__(root, default_dir, mini=True)
        self.root.overrideredirect(True)
        self.root.geometry(bar_geometry(self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        self.popover: tk.Toplevel | None = None
        self.root.bind("<Button-1>", lambda _event: self.toggle_popover())

    def _build_mini_layout(self) -> None:
        self.root.configure(bg=BG)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        bar = tk.Frame(self.root, bg="#111318", padx=14, pady=8, highlightbackground=BORDER, highlightthickness=1)
        bar.grid(row=0, column=0, sticky="nsew")
        bar.columnconfigure(2, weight=1)
        self.status_dot = tk.Label(bar, text="●", bg="#111318", fg=SUCCESS, font=("TkDefaultFont", 13, "bold"))
        self.status_dot.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.local_badge = tk.Label(bar, text="LOCAL", bg="#163225", fg=SUCCESS, font=("TkDefaultFont", 8, "bold"), padx=6, pady=2)
        self.local_badge.grid(row=0, column=1, sticky="w", padx=(0, 8))
        tk.Label(bar, textvariable=self.status_var, bg="#111318", fg=TEXT, font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=0, column=2, sticky="ew")
        tk.Label(bar, textvariable=self.elapsed_var, bg="#111318", fg=TEXT, font=("TkDefaultFont", 12, "bold")).grid(row=0, column=3, padx=(10, 8))
        self.record_button = tk.Button(bar, text="▾", command=self.toggle_popover, bg="#1D2230", fg=TEXT, activebackground="#2B3140", relief="flat", bd=0, padx=10, pady=4, cursor="hand2")
        self.record_button.grid(row=0, column=4)
        self.waveform = WaveformCanvas(bar, height=1)

    def _apply_bar_state(self, gate: SetupGate | None = None, *, saved: bool = False) -> None:
        is_recording = bool(self.recorder and self.recorder.process.poll() is None)
        state = compact_bar_state(gate, recording=is_recording, busy=self.busy, saved=saved)
        colors = {"success": SUCCESS, "warning": WARN, "error": RECORD, "recording": RECORD, "saving": WARN}
        self.status_var.set(state.label)
        if hasattr(self, "status_dot"):
            self.status_dot.config(fg=colors[state.dot_color])
        if hasattr(self, "record_button"):
            command = self.show_stop_sheet if state.button_role == "stop" else (lambda: None if state.button_role == "disabled" else self.toggle_popover())
            self.record_button.config(
                text=state.button_text,
                command=command,
                bg=RECORD if state.button_role == "stop" else "#1D2230",
                state="disabled" if state.button_role == "disabled" else "normal",
            )

    def refresh_setup_state(self) -> SetupGate | None:
        gate = super().refresh_setup_state()
        self._apply_bar_state(gate)
        return gate

    def _update_record_button(self) -> None:
        self._apply_bar_state(None)

    def toggle_recording(self) -> None:
        if self.busy:
            return
        if self.recorder and self.recorder.process.poll() is None:
            self.show_stop_sheet()
        else:
            self.start()
            self.render_popover()

    def toggle_popover(self) -> None:
        if self.popover and self.popover.winfo_exists():
            self.popover.destroy()
            self.popover = None
            return
        self.render_popover()

    def render_popover(self) -> None:
        if self.popover and self.popover.winfo_exists():
            self.popover.destroy()
        self.popover = tk.Toplevel(self.root)
        self.popover.overrideredirect(True)
        self.popover.configure(bg=BG, highlightbackground=BORDER, highlightthickness=1)
        self.popover.attributes("-topmost", True)
        self.popover.geometry(popover_geometry(self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        self.popover.bind("<Escape>", lambda _event: self.toggle_popover())
        outer = ttk.Frame(self.popover, padding=16, style="Panel.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        tk.Label(outer, text="Meeting Recorder", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 18, "bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        tk.Label(outer, text="Local-first audio capture. System audio is the priority; video is optional.", bg=PANEL, fg=MUTED, anchor="w", wraplength=380).grid(row=1, column=0, sticky="ew", pady=(2, 12))
        self._render_popover_body(outer)

    def _render_popover_body(self, parent: tk.Widget) -> None:
        gate = self.refresh_setup_state()
        status_text = gate.message if gate else self.status_var.get()
        color = SUCCESS if gate and gate.status == "ready" else (RECORD if gate and gate.status == "blocked" else WARN)
        tk.Label(parent, text=status_text, bg=PANEL, fg=color, wraplength=390, justify="left", anchor="w").grid(row=2, column=0, sticky="ew", pady=(0, 8))
        next_row = 3
        if gate and (gate.blocking or gate.warnings):
            issues = gate.blocking + [w for w in gate.warnings if w not in gate.blocking]
            issue_text = "\n".join(f"• {issue}" for issue in issues)
            tk.Label(parent, text=issue_text, bg=PANEL, fg=MUTED, wraplength=390, justify="left", anchor="w").grid(row=next_row, column=0, sticky="ew", pady=(0, 10))
            next_row += 1
        if self.last_report and self.last_report.checks:
            indicators = ttk.Labelframe(parent, text="Indicators", style="Section.TLabelframe", padding=8)
            indicators.grid(row=next_row, column=0, sticky="ew", pady=(0, 10))
            indicators.columnconfigure(0, weight=1)
            for idx, check in enumerate(self.last_report.checks):
                style = {"pass": "Pass.TLabel", "warn": "Warn.TLabel", "error": "Error.TLabel"}.get(check.status, "Panel.TLabel")
                ttk.Label(indicators, text=format_check_item(check), style=style, wraplength=370, justify="left").grid(row=idx, column=0, sticky="w", pady=1)
            next_row += 1
        form = ttk.Frame(parent, style="Panel.TFrame")
        form.grid(row=next_row, column=0, sticky="ew")
        next_row += 1
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Meeting name", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(form, text="System audio (meeting/app sound)", variable=self.system_audio_var, command=self.render_popover).grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(form, text="Microphone", variable=self.mic_var, command=self.render_popover).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(form, text="Record screen video (optional)", variable=self.video_var, command=self.render_popover).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(form, text="Transcribe after recording", variable=self.transcribe_var, command=self.render_popover).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(form, text="Summarize after transcript", variable=self.summary_var, command=self.render_popover).grid(row=5, column=0, columnspan=2, sticky="w", pady=4)
        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=next_row, column=0, sticky="ew", pady=(16, 10))
        next_row += 1
        actions.columnconfigure(0, weight=1)
        is_recording = bool(self.recorder and self.recorder.process.poll() is None)
        cta = "Stop & Save Meeting" if is_recording else (gate.suggested_action if gate else "Start Recording")
        bg = RECORD if is_recording else (WARN if gate and not gate.can_start_selected_config else ACCENT)
        command = self._primary_action if not is_recording else self.toggle_recording
        tk.Button(actions, text=cta, command=command, bg=bg, fg=TEXT, activebackground=bg, relief="flat", bd=0, pady=12, font=("TkDefaultFont", 12, "bold"), cursor="hand2").grid(row=0, column=0, sticky="ew")
        if gate and gate.suggested_action == "Record without system audio":
            ttk.Button(actions, text="Uncheck system audio", command=self._record_without_system_audio).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        if gate and gate.suggested_action == "Record without transcript":
            ttk.Button(actions, text="Record without transcript", command=self._record_without_transcript).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        tk.Label(parent, text="Privacy: no uploads by default. Recordings and transcripts stay on this computer.", bg=PANEL, fg=MUTED, wraplength=390, justify="left", anchor="w").grid(row=next_row, column=0, sticky="ew", pady=(8, 0))
        next_row += 1
        if self.current_meeting:
            transcript = "transcript ready" if self.current_meeting.transcript_path.exists() else "transcript skipped/unavailable"
            summary = "summary ready" if self.current_meeting.summary_path.exists() else "summary skipped/unavailable"
            tk.Label(parent, text=f"Saved recording ✓\n{transcript}\n{summary}", bg=PANEL, fg=SUCCESS, wraplength=390, justify="left", anchor="w").grid(row=next_row, column=0, sticky="ew", pady=(12, 0))
            next_row += 1
            ttk.Button(parent, text="Open saved meeting folder", command=lambda: self._open_current("folder")).grid(row=next_row, column=0, sticky="ew", pady=(12, 0))

    def _primary_action(self) -> None:
        gate = self.refresh_setup_state()
        if gate and gate.suggested_action == "Record without system audio":
            self.system_audio_var.set(False)
            self.start()
            self.render_popover()
            return
        if gate and gate.suggested_action == "Record without transcript":
            self.transcribe_var.set(False)
            self.summary_var.set(False)
            self.start()
            self.render_popover()
            return
        if gate and not gate.can_start_selected_config:
            self.render_popover()
            return
        self.start()
        self.render_popover()

    def _record_without_system_audio(self) -> None:
        self.system_audio_var.set(False)
        self.render_popover()

    def _record_without_transcript(self) -> None:
        self.transcribe_var.set(False)
        self.summary_var.set(False)
        self.render_popover()

    def show_stop_sheet(self) -> None:
        if not self.popover or not self.popover.winfo_exists():
            self.render_popover()
        assert self.popover is not None
        for child in self.popover.winfo_children():
            child.destroy()
        frame = ttk.Frame(self.popover, padding=16, style="Panel.TFrame")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        tk.Label(frame, text="Save meeting", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 18, "bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        ttk.Entry(frame, textvariable=self.title_var).grid(row=1, column=0, sticky="ew", pady=(16, 10))
        tk.Button(frame, text="Save", command=self.stop, bg=RECORD, fg=TEXT, relief="flat", bd=0, pady=12, font=("TkDefaultFont", 12, "bold")).grid(row=2, column=0, sticky="ew")

    def _finish(self, stage: str, msg: str, meeting: MeetingFolder | None) -> None:
        super()._finish(stage, msg, meeting)
        self._apply_bar_state(None, saved=bool(meeting and stage == "complete"))
        if self.popover and self.popover.winfo_exists():
            self.render_popover()


def main(default_dir: Path) -> None:
    root = tk.Tk()
    CompactDropdownGUI(root, default_dir)
    root.mainloop()
