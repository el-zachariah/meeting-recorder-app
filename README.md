# Meeting Recorder

Local-first Linux meeting recorder for screen capture, system audio/microphone capture where available, private meeting organization, local transcription fallback, and summaries.

Meeting Recorder is designed for people who want meeting artifacts to stay on their own computer by default. It records into timestamped folders under `~/Meetings`, writes metadata, can transcribe with locally installed Whisper-compatible tools, and can summarize transcripts without sending recordings anywhere.

## 60-second quick start

From the source installer release asset:

```bash
tar -xzf meeting-recorder-app-0.2.0-linux-source-installer.tar.gz
cd meeting-recorder-app-0.2.0
./install.sh
~/.local/bin/meeting-recorder doctor
~/.local/bin/meeting-recorder gui
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
tar -xzf meeting-recorder-app-0.2.0-linux-source-installer.tar.gz
cd meeting-recorder-app-0.2.0
./install.sh
```

This installs to:

- app files: `~/.local/opt/meeting-recorder-app-0.2.0`
- command: `~/.local/bin/meeting-recorder`
- desktop launcher: `~/.local/share/applications/meeting-recorder.desktop`

If `~/.local/bin` is not on your PATH, either add it or run `~/.local/bin/meeting-recorder` directly.

### Option 2: Debian/Ubuntu package

```bash
sudo apt install ./meeting-recorder-app_0.2.0_all.deb
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

- X11 sessions are currently the smoothest capture path because screen recording uses ffmpeg `x11grab`.
- On Wayland, log into an Xorg session or use a compositor/portal-specific recorder until native portal capture is added.
- Audio source detection is best-effort via PulseAudio/PipeWire Pulse compatibility (`pactl`).

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
meeting-recorder record --title demo --size 1920x1080
meeting-recorder record --title demo --display :0.0
meeting-recorder record --title demo --no-system-audio --no-mic
meeting-recorder record --title demo --no-transcribe --no-summary
```

By default recordings are saved under `~/Meetings/YYYY-MM-DD_HH-MM-SS_title/` with:

- `recording.mkv`
- `metadata.json`
- `transcript.txt` when transcription runs or writes fallback instructions
- `summary.md` when summary generation runs

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

Run `meeting-recorder doctor --check audio` and check `pactl list short sources`. PipeWire users may need the Pulse compatibility service. You can always record video only with `--no-system-audio --no-mic`.

### GUI does not start

Install tkinter for your distribution (`python3-tk`, `python3-tkinter`, or `tk`) and run `meeting-recorder doctor --check tkinter`.

### Transcription says unavailable

Install one of the supported local transcription engines. The fallback transcript is intentional and confirms that media was not uploaded.

## Uninstall

User-local installer:

```bash
~/.local/opt/meeting-recorder-app-0.2.0/uninstall.sh
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
