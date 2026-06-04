# Changelog

All notable changes to Meeting Recorder are documented here.

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
