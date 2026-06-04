# Changelog

All notable changes to Meeting Recorder are documented here.

## 0.4.0 - 2026-06-04

### Added

- Audio-first recording is now the default: saves `.mka` meeting audio unless optional screen video is explicitly enabled.
- PulseAudio/PipeWire system-audio monitor detection now prefers the default output monitor and falls back to `ffmpeg -sources pulse` when `pactl` is unavailable.
- Compact notification-bar-style dropdown UI is now the default `meeting-recorder gui` experience, with the full dashboard preserved behind `--full`.
- Setup gating now warns before recording when selected system audio or local transcription is not ready.
- Explicit CLI fallback: `--record-without-transcriber` records without pretending transcription is configured.
- Tests for audio-source fallback, no-input blocking, compact bar state, and parser changes.

### Changed

- Screen video is optional (`--video`) instead of the default path, so the app focuses on meeting/app sound first.
- Missing screen display is a warning for audio-first recording but still blocks selected screen-video workflows.
- Compact UI uses an inline stop/save sheet, local privacy badge, truthful setup state, and post-save artifact status.
- Docs now explain system audio as the speaker/headphone monitor source needed for browser and meeting-app sound.

### Privacy

- The app still uploads nothing by default.
- Transcription remains local-only unless the user installs and selects a local Whisper-compatible engine.
- API summaries remain opt-in and require explicit API environment configuration.

## 0.2.0 - 2026-06-04

### Added

- Professional Linux release identity and documentation.
- Environment doctor with actionable text output, JSON output, and named check filtering.
- CLI meeting library commands: `list`, `show`, and `open`.
- Improved CLI recording options including display selection, JSON result output, open-after-recording, and summary skipping.
- GUI dashboard with setup checklist, capture options, elapsed recording timer, recent meetings, and open actions.
- Release asset builder for source installer tarballs, optional Debian packages, and SHA256 checksums.
- CI workflow that runs tests, compile checks, and release-builder smoke tests.
- Tests for release asset cleanliness and expected installer/package files.

### Changed

- Version updated to `0.2.0`.
- User-facing wording now presents Meeting Recorder as a professional local-first Linux recorder.
- Recording preflight/readiness checks now report ffmpeg/display/screen-size problems more clearly.
- Transcription and summary failures write actionable local artifacts or explicit errors instead of crashing.

### Privacy

- No-upload default privacy model remains unchanged.
- API summarization remains opt-in and requires explicit API environment configuration.

## 0.1.0

- Initial Linux local recording release with CLI launcher, desktop GUI, ffmpeg capture, meeting-folder organization, transcription fallback, and summary generation.
