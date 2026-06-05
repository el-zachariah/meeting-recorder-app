# Changelog

All notable changes to Meeting Recorder are documented here.

## 0.7.2 - 2026-06-05

### Fixed

- Restored the core product shape: `meeting-recorder gui` launches the native system-tray app with hidden root window and tray-opened dropdown, not a standalone Electron/Chromium app window.
- Added regression tests that fail if the GUI entrypoint bypasses `SystemTrayDropdownGUI` or silently falls back when tray dependencies are missing.
- Reinstated Debian runtime dependencies for the tray/Tk GUI path (`python3-tk`, `python3-pystray`, `python3-pil`).

### Changed

- Documented the modern HTML/CSS renderer as screenshot/design evidence only until the modern visual treatment is rebuilt inside the tray/dropdown contract.
- Updated CLI help and package description around the native system-tray workflow.

## 0.7.1 - 2026-06-05

### Fixed

- Made the modern recorder UI interactive by wiring the frontend actions to the local bridge instead of leaving the buttons as static visual evidence.
- Added regression coverage for record, pause/resume, stop/save, setup, and frontend action dispatch paths.

### Release process

- Rebuilt source installer and Debian release assets as v0.7.1.
- Verified screenshots from source checkout and installed/downloaded artifacts.

## 0.7.0 - 2026-06-05

### Changed

- Replaced the rejected Tk/Ttk tray dropdown surface with a modern Electron/WebView-style HTML/CSS UI matching `docs/design/v0.7.0/approved-ui-direction.png`.
- `meeting-recorder gui-screenshot` now renders the modern v0.7.0 UI through a Chromium-compatible headless renderer instead of producing a Tk screenshot or fallback evidence card.
- `meeting-recorder gui` now launches the modern frontend in Electron when available, otherwise Chromium app mode; it no longer starts the Tk/Ttk GUI path.

### Added

- Added a small stdlib Python JSON bridge service for frontend state and UI action dispatch, ready to connect to the existing recorder backend.
- Added modern UI/bridge regression tests and v0.7.0 release evidence documentation.

### Release process

- Updated release asset versioning and documentation to v0.7.0.

## 0.6.0 - 2026-06-05

### Added

- Persistent GUI settings stored in XDG config, including default save location, transcriber model, capture defaults, Obsidian defaults, and post-recording workflow toggles.
- Dropdown now exposes visible Record, Pause, Resume, and Stop controls instead of relying on a single ambiguous toggle.
- Meeting name defaults to a timestamp-based title (`Meeting YYYY-MM-DD HH:MM`) for clearer saved folder names.
- Settings panel for default save location and transcriber settings.
- Best-effort pause/resume support using Linux process pause/resume for ffmpeg, with pause intervals and paused seconds written to meeting metadata.
- COSMIC-aware doctor/tray diagnostics that identify Pop!_OS COSMIC and clearly describe generic AppIndicator/Tk support without claiming native COSMIC integration.

### Release process

- Added tests for persistent settings, pause/resume process control, tray menu actions, and COSMIC diagnostics.
- Updated release docs/evidence targets to v0.6.0.

## 0.5.3 - 2026-06-05

### Fixed

- Hardened `WaveformCanvas` so legacy duplicate/positional height calls cannot crash Tk GUI startup before the tray icon appears.
- Updated native tray dependency guidance and Debian package metadata to include Python GI plus Ayatana/AppIndicator GIR bindings for GNOME/Pop!_OS-style tray visibility.

### Release process

- Added `meeting-recorder gui-screenshot --output <png>` so installed artifacts can produce a real dropdown GUI screenshot/evidence file for release review and user replies.
- CI now smoke-tests `gui-screenshot` from the installed source installer and verifies the release evidence/signoff artifact exists.
- Added `docs/release-evidence/v0.5.3-signoff.md` as the engineer/QA/release-decision signoff record for this candidate.

## 0.5.2 - 2026-06-05

### Fixed

- Fixed Pop!_OS/GNOME tray invisibility caused by creating the AppIndicator tray object while Tk owned the only active mainloop. The GUI now explicitly marks the tray icon visible and pumps pending GLib/AppIndicator events from Tk.
- Added a regression test for the Tk + GLib/AppIndicator event-loop bridge so the app does not silently create an invisible tray icon again.

## 0.5.1 - 2026-06-05

### Fixed

- `meeting-recorder gui` now requires and uses a real native system-tray icon instead of drawing an always-on-top top-right corner bar.
- Clicking the tray icon/default tray action opens the Meeting Recorder dropdown control panel; the main Tk root stays hidden.
- Missing tray dependencies now produce an actionable startup error instead of silently falling back to the wrong UI shape.

### Release process

- Debian packages now depend on `python3-pystray` and `python3-pil` so the installed app has the native tray backend it needs.
- CI installs the tray dependencies before running GUI startup smoke tests.
- Added tray-backend tests so future releases distinguish a real tray icon from a floating corner window.

## 0.5.0 - 2026-06-04

### Changed

- `meeting-recorder gui` is now tray/dropdown-only: removed the legacy `--full` dashboard escape hatch and hidden mini mode from the CLI.
- The dropdown now includes the full setup indicator checklist from the environment doctor instead of hiding those indicators in the removed full dashboard.
- Documentation now describes the tray-style dropdown as the only desktop workflow.

## 0.4.1 - 2026-06-04

### Fixed

- Fixed compact GUI startup crash caused by passing duplicate `height` options into `tkinter.Canvas`.
- Added a regression test for compact waveform height overrides so this exact startup crash cannot return.

### Release process

- CI now installs `xvfb` and runs GUI startup smoke tests under a virtual display.
- CI now smoke-tests the installed source package GUI, not just CLI commands and local unit tests.
- Release workflow checks now use the package version dynamically instead of stale hardcoded release filenames.

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
