from __future__ import annotations

from pathlib import Path
from datetime import datetime
import os
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, filedialog

from .organizer import organize_recording
from .recorder import start_recording, stop_recording, RecorderProcess
from .summarizer import summarize_transcript
from .transcription import transcribe


class MeetingRecorderGUI:
    def __init__(self, root: tk.Tk, default_dir: Path):
        self.root = root
        self.root.title("Meeting Recorder MVP")
        self.default_dir = Path(default_dir).expanduser()
        self.recorder: RecorderProcess | None = None
        self.raw_file: Path | None = None

        self.title_var = tk.StringVar(value="meeting")
        self.dir_var = tk.StringVar(value=str(self.default_dir))
        self.status_var = tk.StringVar(value="Ready. No uploads; local recording/transcription only.")

        tk.Label(root, text="Meeting title").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        tk.Entry(root, textvariable=self.title_var, width=45).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(root, text="Output folder").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        tk.Entry(root, textvariable=self.dir_var, width=45).grid(row=1, column=1, padx=8, pady=6)
        tk.Button(root, text="Browse", command=self.browse).grid(row=1, column=2, padx=8, pady=6)
        self.start_button = tk.Button(root, text="Start Recording", command=self.start)
        self.start_button.grid(row=2, column=0, padx=8, pady=10)
        self.stop_button = tk.Button(root, text="Stop + Organize", command=self.stop, state="disabled")
        self.stop_button.grid(row=2, column=1, padx=8, pady=10)
        tk.Label(root, textvariable=self.status_var, wraplength=520, justify="left").grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=8)

    def browse(self):
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or str(self.default_dir))
        if chosen:
            self.dir_var.set(chosen)

    def start(self):
        try:
            raw_dir = Path(tempfile.mkdtemp(prefix="meeting-recorder-raw-"))
            raw_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(raw_dir, 0o700)
            self.raw_file = raw_dir / f"gui-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.mkv"
            self.recorder = start_recording(self.raw_file)
        except Exception as exc:
            messagebox.showerror("Could not start recording", str(exc))
            return
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("Recording... click Stop + Organize when done.")

    def stop(self):
        if not self.recorder or not self.raw_file:
            return
        self.stop_button.config(state="disabled")
        self.status_var.set("Stopping, organizing, transcribing if possible, and summarizing...")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stop_worker(self):
        try:
            stop_recording(self.recorder)  # type: ignore[arg-type]
            meeting = organize_recording(self.raw_file, Path(self.dir_var.get()), self.title_var.get())  # type: ignore[arg-type]
            try:
                self.raw_file.parent.rmdir()  # type: ignore[union-attr]
            except OSError:
                pass
            transcribe(meeting.media_path, meeting.transcript_path)  # type: ignore[arg-type]
            summarize_transcript(meeting.transcript_path, meeting.summary_path)
            msg = f"Done: {meeting.path}"
        except Exception as exc:
            msg = f"Error: {exc}"
        self.root.after(0, lambda: self._finish(msg))

    def _finish(self, msg: str):
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set(msg)


def main(default_dir: Path):
    root = tk.Tk()
    MeetingRecorderGUI(root, default_dir)
    root.mainloop()
