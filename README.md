# Meeting Recorder

Local-first Linux meeting recorder for screen capture, system audio/microphone capture where available, private meeting organization, local transcription fallback, summaries, Obsidian export, and Claude/Codex-ready prompt export.

Meeting Recorder is designed for people who want meeting artifacts to stay on their own computer by default. It records into timestamped folders under `~/Meetings`, writes metadata, can transcribe with locally installed Whisper-compatible tools, and can summarize transcripts without sending recordings anywhere.

## 60-second quick start

From the source installer release asset:

```bash
tar -xzf meeting-recorder-app-0.4.0-linux-source-installer.tar.gz
cd meeting-recorder-app-0.4.0
./install.sh
~/.local/bin/meeting-recorder doctor
~/.local/bin/meeting-recorder gui
# Optional legacy full dashboard:
~/.local/bin/meeting-recorder gui --full
```

Record from the CLI:

```bash
meeting-recorder record --title "team-sync" --open
# Press Enter to stop recording.
```

Review saved meetings:

```bash
meeting-recorder list
meeting-recorder show <meeting-id>
meeting-recorder open <meeting-id> --target summary
```

## Install options

### Option 1: user-local source installer (recommended for most Linux users)

```bash
tar -xzf meeting-recorder-app-0.4.0-linux-source-installer.tar.gz
cd meeting-recorder-app-0.4.0
./install.sh
```

This installs to:

- app files: `~/.local/opt/meeting-recorder-app-0.4.0`
- command: `~/.local/bin/meeting-recorder`
- desktop launcher: `~/.local/share/applications/meeting-recorder.desktop`

If `~/.local/bin` is not on your PATH, either add it or run `~/.local/bin/meeting-recorder` directly.

### Option 2: Debian/Ubuntu package

```bash
sudo apt install ./meeting-recorder-app_0.4.0_all.deb
meeting-recorder doctor
meeting-recorder gui
```

The `.deb` declares dependencies on `python3`, `python3-tk`, and `ffmpeg`.

### Option 3: run from a source checkout

```bash
git clone <repo-url> meeting-recorder-app
cd meeting-recorder-app
./meeting-recorder doctor
./meeting-recorder gui
```

## Distro dependencies

Meeting Recorder has no required Python package dependencies, but it relies on system tools for capture and desktop UI.

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-tk ffmpeg pulseaudio-utils x11-utils
```

Fedora:

```bash
sudo dnf install python3 python3-tkinter ffmpeg pulseaudio-utils xorg-x11-utils
```

Arch Linux:

```bash
sudo pacman -S python tk ffmpeg libpulse xorg-xdpyinfo
```

Notes:

- Screen video is optional (`meeting-recorder record --video` or the GUI checkbox). Audio-only recording does not require X11 `DISPLAY`.
- On Wayland, audio-first recording still works through PulseAudio/PipeWire when a monitor source exists; screen video still needs X11/XWayland until native portal capture is added.
- Audio source detection uses PulseAudio/PipeWire Pulse compatibility through `pactl` when available and falls back to `ffmpeg -sources pulse`.

## First-run setup

Run the environment doctor before recording:

```bash
meeting-recorder doctor
meeting-recorder doctor --json
meeting-recorder doctor --check ffmpeg --check display
```

The doctor checks ffmpeg, display/session state, screen size detection, audio sources, tkinter, transcription engines, output directory permissions, and privacy mode.

Common capture options:

```bash
meeting-recorder record --title demo
meeting-recorder record --title demo --video --size 1920x1080
meeting-recorder record --title demo --video --display :0.0
meeting-recorder record --title demo --no-mic
meeting-recorder record --title screen-only --video --no-system-audio --no-mic
meeting-recorder record --title demo --no-transcribe --no-summary
meeting-recorder record --title demo --record-without-transcriber  # explicit recording-only fallback when Whisper is missing
```

By default recordings are saved under `~/Meetings/YYYY-MM-DD_HH-MM-SS_title/` with:

- `recording.mka` for the default audio-first mode, or `recording.mkv` when screen video is enabled
- `metadata.json`
- `transcript.txt` when transcription runs or writes fallback instructions
- `summary.md` when summary generation runs


## Modern desktop workflow

The v0.4.0 GUI now launches as a compact, always-on-top recorder bar near the top-right of the screen. Click the bar to open the dropdown-style control panel. The panel focuses on what matters for meetings:

- system audio capture status, with a clear warning if meeting/app sound will not be recorded
- microphone status
- optional screen video checkbox, off by default
- local transcriber readiness, with an explicit record-without-transcript action when Whisper is not installed
- inline stop/save naming instead of a retro pop-up dialog

```bash
meeting-recorder gui
meeting-recorder gui --full   # legacy dashboard window
```

Linux native tray APIs vary by desktop environment, so v0.4.0 keeps the dependency-free top-corner dropdown as the default instead of depending on fragile tray packages.

## Obsidian export

Export a saved meeting into an Obsidian vault as a Markdown note with YAML frontmatter, summary, transcript content, and local file links:

```bash
meeting-recorder export-obsidian latest --vault ~/Obsidian/MyVault --folder Meetings
```

By default media is linked from its local meeting folder instead of copied into your vault, which avoids bloating Obsidian Sync or other synced vaults. If you intentionally want copies, use `--copy-text-artifacts` for transcript/summary copies or `--copy-media` for recording media.

## Claude/Codex prompt export

Meeting Recorder does **not** scrape Claude Code or Codex credentials and does not treat those developer tools as hidden transcription APIs. Instead, it can write a local prompt that you can paste into Claude, Claude Code, Codex, or ChatGPT yourself:

```bash
meeting-recorder export-ai-prompt latest --target claude-code
meeting-recorder export-ai-prompt latest --target codex
```

This keeps account access under your control and makes any cloud AI use explicit.

## Local transcription

Transcription runs only when a compatible local engine is installed. If none is found, Meeting Recorder writes a clear `transcript.txt` explaining what to install rather than uploading media.

Supported local engine paths include:

- Python `faster-whisper` package
- `whisper.cpp` command names such as `whisper-cli`, `main`, or `whisper.cpp`
- OpenAI Whisper local CLI command `whisper`

Example with an isolated development environment:

```bash
uv venv
uv pip install faster-whisper
meeting-recorder transcribe --media ~/Meetings/<meeting-folder>/recording.mkv --model base
meeting-recorder summarize --transcript ~/Meetings/<meeting-folder>/transcript.txt
```

Model names such as `base` may cause the selected local engine to download model files. For offline use, download and verify a model yourself, pass the local model path, and set:

```bash
MEETING_RECORDER_OFFLINE=1 meeting-recorder transcribe --media recording.mkv --model /path/to/model
```

## Privacy model

- No uploads by default.
- Recordings, metadata, transcripts, and summaries are stored locally.
- Temporary raw recording directories are created with user-only permissions where practical.
- Meeting folders and artifacts are created with private permissions where practical.
- API summaries are disabled unless you explicitly pass `summarize --use-api` and provide `OPENAI_BASE_URL` plus `OPENAI_API_KEY`.
- Claude/Codex prompt export writes a local Markdown prompt only; it does not read credentials or upload anything.
- Obsidian export writes local Markdown notes and file links by default; copying media into a synced vault is opt-in.

Opt-in API summary example:

```bash
export OPENAI_BASE_URL="https://your-compatible-endpoint/v1"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o-mini"
meeting-recorder summarize --transcript transcript.txt --use-api
```

## Troubleshooting

### `doctor` reports ffmpeg missing

Install `ffmpeg` with your distro package manager and rerun `meeting-recorder doctor`.

### Screen capture fails or output is empty

Check that you are in an X11 session and that `DISPLAY` is set:

```bash
echo "$XDG_SESSION_TYPE $DISPLAY"
meeting-recorder doctor --check display --check screen_size
```

If auto-detection fails, pass `--size WIDTHxHEIGHT` and optionally `--display :0.0`.

### No system audio or microphone is captured

Run `meeting-recorder doctor --check system_audio --check microphone`. System audio means the PulseAudio/PipeWire monitor source for your speakers/headphones; without it, browser/video-call audio will not be recorded. The app now blocks selected system-audio recording when no monitor is detected instead of silently saving a video-only file. Install `pulseaudio-utils`, make sure `pipewire-pulse` or PulseAudio is running, then refresh setup. If you intentionally want mic-only recording, use `--no-system-audio` or uncheck System audio in the GUI.

### GUI does not start

Install tkinter for your distribution (`python3-tk`, `python3-tkinter`, or `tk`) and run `meeting-recorder doctor --check tkinter`.

### Transcription says unavailable

Install one of the supported local transcription engines. The fallback transcript is intentional and confirms that media was not uploaded.

## Uninstall

User-local installer:

```bash
~/.local/opt/meeting-recorder-app-0.4.0/uninstall.sh
```

Debian/Ubuntu package:

```bash
sudo apt remove meeting-recorder-app
```

Source checkout:

```bash
rm -rf /path/to/meeting-recorder-app
```

Your meeting recordings are not removed by uninstall commands. Delete `~/Meetings` manually if you no longer want the local data.

## Development

```bash
cd meeting-recorder-app
pytest -q
python3 -m compileall src scripts
python3 scripts/build_release_assets.py
```

Release artifacts are written to `dist/` and checksums to `dist/SHA256SUMS`.
Verify them with `(cd dist && sha256sum -c SHA256SUMS)`.
