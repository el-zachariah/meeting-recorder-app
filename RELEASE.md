# Release guide

This project ships Linux release assets for Meeting Recorder v0.5.0. Do not publish from automation in this repository without an explicit release decision; the builder only creates local artifacts.

## Assets

The release builder creates:

- `dist/meeting-recorder-app-0.5.0-linux-source-installer.tar.gz`
- `dist/meeting-recorder-app_0.5.0_all.deb` when `dpkg-deb` is installed
- `dist/SHA256SUMS`

The source installer contains app source, docs, tests, `install.sh`, `uninstall.sh`, `meeting-recorder.desktop`, and the launcher wrapper. It excludes git metadata, caches, virtual environments, build output, previous release artifacts, egg-info, bytecode, and private meeting data.

## Local verification checklist

```bash
pytest -q
python3 -m compileall src scripts
./meeting-recorder --help
./meeting-recorder doctor || true
./meeting-recorder doctor --json || true
./meeting-recorder list --output-dir "$(mktemp -d)"
python3 scripts/build_release_assets.py
(cd dist && sha256sum -c SHA256SUMS)
```

Tarball install smoke test:

```bash
TMP_HOME=$(mktemp -d)
TMP_PREFIX=$(mktemp -d)
tar -xzf dist/meeting-recorder-app-0.5.0-linux-source-installer.tar.gz -C "$TMP_HOME"
(cd "$TMP_HOME/meeting-recorder-app-0.5.0" && HOME="$TMP_HOME" PREFIX="$TMP_PREFIX" ./install.sh)
HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" --help
HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" doctor || true
if command -v xvfb-run >/dev/null 2>&1; then
  timeout 8s xvfb-run -a env HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" gui || code=$?
  test "${code:-0}" = "124"
fi
HOME="$TMP_HOME" PREFIX="$TMP_PREFIX" "$TMP_PREFIX/opt/meeting-recorder-app-0.5.0/uninstall.sh"
```

Debian package inspection, when available:

```bash
dpkg-deb --info dist/meeting-recorder-app_0.5.0_all.deb
dpkg-deb --contents dist/meeting-recorder-app_0.5.0_all.deb
```

## Publishing notes

1. Start from a clean git working tree.
2. Run the local verification checklist.
3. Inspect `dist/SHA256SUMS` and package contents.
4. Create and push tag `v0.5.0` only after approval.
5. Upload the source installer, Debian package when built, and SHA256SUMS to the GitHub release.

Publish only after the release gate passes: tests, package build, checksum verification, GitHub upload, downloaded-asset verification, and honest known limitations.
