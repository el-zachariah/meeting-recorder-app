# Changelog

All notable changes to Meeting Recorder are documented here.

## 0.3.0 - 2026-06-04

### Added

- Modern dark recorder-first GUI with large record/stop control, elapsed timer, privacy badge, and waveform-style activity indicator.
- Compact `meeting-recorder gui --mini` always-on-top corner controller.
- Stop-time meeting naming flow and richer metadata: start/end time, duration, network/provider/model audit fields, and uploaded-artifacts list.
- Obsidian vault export via `meeting-recorder export-obsidian`, with frontmatter, transcript/summary content, and local file links.
- Claude/Codex-ready prompt export via `meeting-recorder export-ai-prompt` without reading account credentials.
- Tests for Obsidian export, AI prompt export, modern GUI helper models, metadata, and new CLI commands.

### Changed

- GUI now emphasizes daily-use recording workflow first, with setup/capture/export details still available.
- Meeting folders can be renamed around the stop/end time to match how users remember meetings.
- Privacy documentation now explicitly distinguishes local prompt export from cloud/API account integration.

### Privacy

- The app still uploads nothing by default.
- Claude Code/Codex accounts are not scraped or automated; prompt export is a local file workflow.
- Obsidian export links media by default instead of copying recordings into potentially synced vaults.

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
