# Meeting Recorder App MVP

A Linux-first, privacy-first local desktop/tool app for recording your screen, system audio and microphone when available, organizing recordings into timestamped meeting folders, transcribing locally with installed Whisper-compatible tools, and generating summaries.

## Privacy

- **No uploads by default.** Recording, file organization, transcription fallback, and extractive summaries run locally.
- The app only uses an OpenAI-compatible API if you explicitly pass `summarize --use-api` **and** set `OPENAI_BASE_URL` plus `OPENAI_API_KEY`.
- Temporary raw recordings are created in a new private `0700` temp directory per recording, then moved into the meeting folder.
- Meeting folders are created with user-only permissions (`0700`), and media/metadata files are set to `0600` where practical.
- Your recordings are stored under `~/Meetings` by default, or a folder you choose.

## What works in this MVP

- CLI launcher: `./meeting-recorder`
- Simple Tk desktop GUI: `./meeting-recorder gui`
- Linux screen recording via `ffmpeg` `x11grab`.
- Best-effort PulseAudio/PipeWire Pulse source detection for system audio monitor and microphone.
- On stop: moves media into `YYYY-MM-DD_HH-MM-SS_title/recording.mkv` with `metadata.json`.
- Local transcription if a compatible engine is installed:
  - Python `faster-whisper` package, preferred
  - `whisper.cpp` CLI (`whisper-cli`, `main`, or `whisper.cpp` on PATH)
  - OpenAI Whisper local CLI (`whisper` on PATH)
- Graceful no-op transcription fallback with install instructions.
- Local extractive/template summary in `summary.md`.
- Tests for organization, transcription fallback, and summarization.

## Requirements

- Linux
- Python 3.10+
- `ffmpeg` installed and on PATH
- X11 session for screen capture (`x11grab`). Wayland users may need to log into an Xorg session or adapt capture tooling.
- Optional: PulseAudio/PipeWire Pulse compatibility for audio source auto-detection.
- Optional: `tkinter` for GUI (`python3-tk` on many distros).

## Quick start from release tarball

```bash
tar -xzf meeting-recorder-app-0.1.0.tar.gz
cd meeting-recorder-app-0.1.0
./meeting-recorder status
./meeting-recorder gui
```

CLI recording:

```bash
./meeting-recorder record --title "team-sync" --size 1920x1080
# Press Enter to stop.
```

If screen size differs:

```bash
MEETING_RECORDER_SIZE=1366x768 ./meeting-recorder record --title demo
```

Disable audio if needed:

```bash
./meeting-recorder record --title demo --no-system-audio --no-mic
```

## Transcription

Recordings are transcribed locally only when a local engine is installed. Otherwise `transcript.txt` contains instructions and no audio/video is uploaded.

Recommended local engine:

```bash
uv venv
uv pip install faster-whisper
./meeting-recorder transcribe --media ~/Meetings/<meeting-folder>/recording.mkv
```

Important: passing a model name such as `base` can cause `faster-whisper` or the OpenAI Whisper CLI to download model files the first time. That still does **not** upload your recordings, but it is network access. For fully offline use, download and verify a model yourself, pass its local path with `--model`, and run with:

```bash
MEETING_RECORDER_OFFLINE=1 ./meeting-recorder transcribe --media ~/Meetings/<meeting-folder>/recording.mkv --model /path/to/local/model
```

Then summarize:

```bash
./meeting-recorder summarize --transcript ~/Meetings/<meeting-folder>/transcript.txt
```

## Optional API summary opt-in

This is disabled unless you explicitly opt in:

```bash
export OPENAI_BASE_URL="https://your-compatible-endpoint/v1"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o-mini"
./meeting-recorder summarize --transcript transcript.txt --use-api
```

## Development and tests

```bash
cd /home/zachariah/meeting-recorder-app
pytest -q
./meeting-recorder status
```

## Known limitations

- MVP targets Linux/X11. Wayland capture may require a portal-based recorder such as OBS, wf-recorder, or desktop-specific tools.
- Audio mixing is best-effort based on `pactl list short sources`.
- `whisper.cpp` deployments vary; if your build needs custom model flags, use `faster-whisper` for the smoothest path or adapt `transcription.py`.
- This is an early MVP release; GitHub hosts the source and downloadable tarball.
