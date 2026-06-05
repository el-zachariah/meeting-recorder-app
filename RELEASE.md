# Release guide

This project ships Linux release assets for Meeting Recorder. Do not publish from automation in this repository without an explicit release decision; the builder only creates local artifacts.

## Assets

The release builder creates:

- `dist/meeting-recorder-app-0.7.0-linux-source-installer.tar.gz`
- `dist/meeting-recorder-app_0.7.0_all.deb` when `dpkg-deb` is installed
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

Create the release lifecycle evidence/signoff artifact before publishing. Keep it
in `docs/release-evidence/` and attach a copy or the generated bundle to the
release notes after approval:

```bash
cp docs/release-evidence/v0.7.0-signoff.md /tmp/meeting-recorder-v0.7.0-signoff.md
```

Tarball install smoke test:

```bash
TMP_HOME=$(mktemp -d)
TMP_PREFIX=$(mktemp -d)
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")

tar -xzf "dist/meeting-recorder-app-${VERSION}-linux-source-installer.tar.gz" -C "$TMP_HOME"
(cd "$TMP_HOME/meeting-recorder-app-${VERSION}" && HOME="$TMP_HOME" PREFIX="$TMP_PREFIX" ./install.sh)
HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" --help
HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" doctor || true
HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" gui-screenshot --output "$TMP_HOME/meeting-recorder-gui.png"
test -s "$TMP_HOME/meeting-recorder-gui.png"
if command -v chromium >/dev/null 2>&1 || command -v electron >/dev/null 2>&1; then
  timeout 8s env HOME="$TMP_HOME" "$TMP_PREFIX/bin/meeting-recorder" gui || code=$?
  test "${code:-0}" = "124" || test "${code:-0}" = "0"
fi
HOME="$TMP_HOME" PREFIX="$TMP_PREFIX" "$TMP_PREFIX/opt/meeting-recorder-app-${VERSION}/uninstall.sh"
```

Debian package inspection, when available:

```bash
dpkg-deb --info "dist/meeting-recorder-app_${VERSION}_all.deb"
dpkg-deb --contents "dist/meeting-recorder-app_${VERSION}_all.deb"
```

## Publishing notes

1. Start from a clean git working tree.
2. Run the local verification checklist.
3. Inspect `dist/SHA256SUMS` and package contents.
4. Create and push tag `v${VERSION}` only after approval.
5. Upload the source installer, Debian package when built, and SHA256SUMS to the GitHub release.

Publish only after the release gate passes: tests, package build, checksum verification, engineer signoff, QA/research signoff, GitHub upload, downloaded-asset verification, GUI screenshot/evidence, and honest known limitations.
