# Meeting Recorder Professional v0.2.0 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Turn the prototype into a polished first professional Linux release that is easy to install, easy to set up, easy to use, privacy-forward, and verified by tests/release gates.

**Architecture:** Keep the stdlib Python app lightweight. Add testable service modules for environment checks, meeting library, app config, opening files, and release building. Upgrade CLI and Tk/ttk GUI to use those shared modules.

**Tech Stack:** Python 3.10+, tkinter/ttk, ffmpeg, argparse, pytest, dpkg-deb when available, GitHub releases.

---

## Acceptance gates

- User-facing surfaces no longer use prototype-era wording.
- `meeting-recorder doctor` gives actionable pass/warn/error checks and JSON output.
- `meeting-recorder list/show/open` provide a usable meeting library from CLI.
- GUI has a dashboard: setup checklist, capture options, elapsed recording timer, progress stages, recent meetings, open actions.
- Recording has better preflight/readiness handling and screen-size detection.
- Transcription/summary failures write clear local artifacts instead of crashing.
- Installer tarball and `.deb` build reproducibly and install usable launchers.
- Release artifact excludes `.git`, caches, build output, venvs, generated private data.
- Tests cover status, library, recorder command building, CLI commands, permissions, packaging cleanliness.
- Final release is tagged `v0.2.0` and GitHub release assets are uploaded.

## Round 1 — Foundations, setup, and CLI

### Task 1: Status/doctor service
- Create `src/meeting_recorder/status.py` with `CheckItem`, `EnvironmentReport`, `build_environment_report`, `format_report_text`.
- Detect ffmpeg, x11/wayland/display, screen size, audio sources, tkinter availability, transcription engines, output dir writability, privacy mode.
- Add tests in `tests/test_status.py`.

### Task 2: Meeting library service
- Create `src/meeting_recorder/library.py` with `MeetingListItem`, `scan_meetings`, `resolve_meeting_path`, `describe_meeting`, `open_path`.
- Read metadata when present, fall back gracefully.
- Add tests in `tests/test_library.py`.

### Task 3: CLI polish
- Modify `src/meeting_recorder/cli.py`:
  - rename description to “Local-first Linux meeting recorder”;
  - add `doctor` alias/enhanced command with `--json` and `--check`;
  - add `list`, `show`, `open` commands;
  - improve `status` to use doctor output;
  - add `record --open`, `--no-summary`, `--display`, `--json`.
- Add parser/command tests in `tests/test_cli_parser.py` and `tests/test_cli_commands.py`.

### Task 4: Recorder reliability
- Modify `src/meeting_recorder/recorder.py`:
  - auto-detect X11 screen size using `xdpyinfo` where available;
  - expose display option;
  - preflight ffmpeg existence/display errors;
  - drain stderr safely to a temp log;
  - readiness check shortly after start;
  - keep subprocess argument lists.
- Add tests in `tests/test_recorder.py`.

## Round 2 — GUI/UX

### Task 5: GUI dashboard
- Rewrite `src/meeting_recorder/gui.py` around ttk sections: privacy header, setup checklist, recording controls, recent meetings, completion actions.
- Include title/output/fps/size/system-audio/mic/transcribe checkboxes.
- Show elapsed timer while recording.
- Show staged progress and buttons to open folder/transcript/summary.
- Add headless-safe pure formatting helpers and tests in `tests/test_gui_models.py`.

### Task 6: Transcription and summary UX hardening
- Ensure transcription engine failures produce a clear `transcript.txt` failure report, not an uncaught crash.
- Make `summarize --use-api` without env vars return explicit error.
- Update summaries for unavailable/failed transcripts.
- Add tests in transcription/summarizer/CLI tests.

## Round 3 — Installers, docs, release automation

### Task 7: Installer/release builder
- Create `scripts/build_release_assets.py`.
- Build clean source installer tarball with `install.sh`, `uninstall.sh`, `.desktop`, launcher wrapper.
- Build Debian package when `dpkg-deb` exists.
- Generate `dist/SHA256SUMS`.
- Add tests in `tests/test_release_assets.py` for excluded caches and expected files.

### Task 8: Documentation and release identity
- Update `pyproject.toml` to `0.2.0` and remove prototype-era wording.
- Rewrite README for 60-second quick start, install options, distro deps, first-run setup, privacy, troubleshooting, uninstall.
- Add `CHANGELOG.md` and `RELEASE.md`.
- Add `.github/workflows/ci.yml` for pytest and artifact builder smoke test.

### Task 9: Final verification and publish
- Clean generated files/caches.
- Run full gates: pytest, compileall, CLI help/status/doctor/list, clean temp install, build assets, extract/install tarball, inspect deb, security scan.
- Commit verified changes.
- Push to GitHub, tag `v0.2.0`, create GitHub release with source installer tarball, `.deb`, SHA256SUMS.
