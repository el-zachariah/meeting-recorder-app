# Linux packaging recommendation

## Recommendation

Ship two release assets for v0.2.0:

1. **Primary, distro-agnostic asset:** `meeting-recorder-app-0.2.0-linux-source-installer.tar.gz` containing app source, launcher, documentation, `install.sh`, `uninstall.sh`, and `meeting-recorder.desktop`. The installer copies the app to `~/.local/opt/meeting-recorder-app-0.2.0`, creates `~/.local/bin/meeting-recorder`, and installs a per-user desktop launcher in `~/.local/share/applications`.
2. **Professional convenience asset for Debian/Ubuntu users:** `meeting-recorder-app_0.2.0_all.deb` with dependencies on `python3 (>= 3.10)`, `python3-tk`, and `ffmpeg`, installing the app under `/opt/meeting-recorder-app`, `/usr/bin/meeting-recorder`, and `/usr/share/applications/meeting-recorder.desktop`.

This route avoids AppImage complexity while giving users an easy download/install/run path, a desktop launcher, checksums, and CI-verifiable artifacts.

## Option assessment

### Tarball + install.sh + .desktop

**Pros:** distro-agnostic, no root required, small, simple to debug, works with the existing no-required-Python-dependency source layout, easy to verify in CI, and installs a real desktop launcher.

**Cons:** still relies on system `python3`, `python3-tk`, and `ffmpeg`; users on minimal installs may need package-manager commands. Optional transcription engines remain separate.

**Fit:** best first-release default.

### pipx / uv

**Pros:** familiar Python packaging workflow and good for CLI-oriented users.

**Cons:** does not solve `ffmpeg` or `python3-tk`; does not naturally install a desktop launcher; requires a separate package publishing story.

**Fit:** good secondary developer/CLI install path after the desktop release path is established.

### AppImage

**Pros:** one-file desktop artifact if done well.

**Cons:** bundling Python, tkinter, ffmpeg, optional transcription engines, and model/GPU libraries is substantially more involved. Building on a very new distro can also create glibc compatibility problems for older Linux users.

**Fit:** defer until after the first professional release.

### .deb

**Pros:** professional install/uninstall UX for Debian/Ubuntu; can declare `ffmpeg` and `python3-tk` dependencies; standard desktop launcher integration.

**Cons:** Debian/Ubuntu-specific; requires root/admin install; package signing and repositories are additional work.

**Fit:** ship alongside the source installer as a convenience asset.

## Release hardening now implemented

- `scripts/build_release_assets.py` builds the source installer, optional Debian package, and `SHA256SUMS`.
- Release tests verify expected files and packaging cleanliness.
- CI runs pytest, compile checks, CLI smoke tests, builder smoke tests, checksum verification, and artifact inspection.
- `README.md` and `RELEASE.md` document install, verification, privacy, troubleshooting, and uninstall flows.
