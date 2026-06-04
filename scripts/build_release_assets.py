#!/usr/bin/env python3
"""Build release assets for Meeting Recorder.

Outputs:
- dist/meeting-recorder-app-<version>-linux-source-installer.tar.gz
- dist/meeting-recorder-app_<version>_all.deb when dpkg-deb is available
- dist/SHA256SUMS
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import tomllib
from typing import Iterable

PROJECT_SLUG = "meeting-recorder-app"
COMMAND_NAME = "meeting-recorder"
PACKAGE_NAME = "meeting-recorder-app"
APP_LABEL = "Meeting Recorder"
APP_ID = "meeting-recorder"
DEFAULT_EPOCH = 1_704_067_200  # 2024-01-01T00:00:00Z

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "build",
    "dist",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_PART_SUFFIXES = {".egg-info"}
PRIVATE_DATA_NAMES = {"Meetings", "meeting-recorder-raw"}

ROOT_FILES = [
    "README.md",
    "CHANGELOG.md",
    "RELEASE.md",
    "PACKAGING_RECOMMENDATION.md",
    "LICENSE",
    "pyproject.toml",
    "meeting-recorder",
]
ROOT_DIRS = ["src", "tests", "docs", "scripts", ".github"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def is_excluded(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(part in EXCLUDED_DIR_NAMES for part in parts):
        return True
    if any(part.endswith(tuple(EXCLUDED_PART_SUFFIXES)) for part in parts):
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    if any(part in PRIVATE_DATA_NAMES for part in parts):
        return True
    return False


def iter_source_files(root: Path) -> Iterable[Path]:
    for name in ROOT_FILES:
        path = root / name
        if path.exists() and not is_excluded(path, root):
            yield path
    for dirname in ROOT_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not is_excluded(path, root):
                yield path


def copy_source_tree(root: Path, target: Path) -> None:
    for source in iter_source_files(root):
        rel = source.relative_to(root)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def desktop_file(exec_cmd: str, icon: str = "applications-multimedia") -> str:
    return f"""[Desktop Entry]\nType=Application\nName={APP_LABEL}\nComment=Local-first Linux meeting recorder\nExec={exec_cmd} gui\nIcon={icon}\nTerminal=false\nCategories=AudioVideo;Recorder;Utility;\nKeywords=meeting;recording;screen;audio;transcription;\nStartupNotify=true\n"""


def install_script(version: str) -> str:
    return f'''#!/usr/bin/env bash
set -euo pipefail
APP_NAME="{PROJECT_SLUG}"
VERSION="{version}"
PREFIX="${{PREFIX:-$HOME/.local}}"
APP_DIR="$PREFIX/opt/$APP_NAME-$VERSION"
BIN_DIR="$PREFIX/bin"
DESKTOP_DIR="$PREFIX/share/applications"
SOURCE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
cp -a "$SOURCE_DIR"/. "$APP_DIR"/
rm -f "$APP_DIR/install.sh"
chmod +x "$APP_DIR/meeting-recorder" || true

cat > "$BIN_DIR/{COMMAND_NAME}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$APP_DIR"
export PYTHONPATH="\\$APP_DIR/src\\${{PYTHONPATH:+:\\$PYTHONPATH}}"
exec python3 -m meeting_recorder.cli "\\$@"
EOF
chmod +x "$BIN_DIR/{COMMAND_NAME}"

cat > "$DESKTOP_DIR/{APP_ID}.desktop" <<EOF
{desktop_file(f'$BIN_DIR/{COMMAND_NAME}').rstrip()}
EOF

printf 'Installed {APP_LABEL} %s to %s\n' "$VERSION" "$APP_DIR"
printf 'Run: %s doctor\n' "$BIN_DIR/{COMMAND_NAME}"
printf 'Uninstall: %s/uninstall.sh\n' "$APP_DIR"
'''


def uninstall_script(version: str) -> str:
    return f'''#!/usr/bin/env bash
set -euo pipefail
APP_NAME="{PROJECT_SLUG}"
VERSION="{version}"
PREFIX="${{PREFIX:-$HOME/.local}}"
rm -rf "$PREFIX/opt/$APP_NAME-$VERSION"
rm -f "$PREFIX/bin/{COMMAND_NAME}"
rm -f "$PREFIX/share/applications/{APP_ID}.desktop"
printf 'Uninstalled {APP_LABEL} %s from %s\n' "$VERSION" "$PREFIX"
'''


def add_tar_entry(tar: tarfile.TarFile, path: Path, arcname: str, epoch: int) -> None:
    info = tar.gettarinfo(str(path), arcname=arcname)
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = epoch
    if path.is_file():
        with path.open("rb") as fh:
            tar.addfile(info, fh)
    else:
        tar.addfile(info)


def build_source_installer(root: Path, dist: Path, version: str, epoch: int) -> Path:
    asset = dist / f"{PROJECT_SLUG}-{version}-linux-source-installer.tar.gz"
    with tempfile.TemporaryDirectory(prefix="meeting-recorder-release-") as td:
        staging_root = Path(td) / f"{PROJECT_SLUG}-{version}"
        staging_root.mkdir(parents=True)
        copy_source_tree(root, staging_root)
        write_executable(staging_root / "install.sh", install_script(version))
        write_executable(staging_root / "uninstall.sh", uninstall_script(version))
        (staging_root / "meeting-recorder.desktop").write_text(desktop_file(f"$HOME/.local/bin/{COMMAND_NAME}"), encoding="utf-8")
        with tarfile.open(asset, "w:gz", compresslevel=9) as tar:
            for path in sorted(staging_root.rglob("*")):
                rel = path.relative_to(staging_root.parent)
                add_tar_entry(tar, path, rel.as_posix(), epoch)
    return asset


def build_deb(root: Path, dist: Path, version: str, epoch: int) -> Path | None:
    if shutil.which("dpkg-deb") is None:
        return None
    asset = dist / f"{PACKAGE_NAME}_{version}_all.deb"
    with tempfile.TemporaryDirectory(prefix="meeting-recorder-deb-") as td:
        package_root = Path(td) / "pkg"
        app_dir = package_root / "opt" / PROJECT_SLUG
        copy_source_tree(root, app_dir)
        write_executable(package_root / "usr" / "bin" / COMMAND_NAME, '''#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/meeting-recorder-app"
export PYTHONPATH="$APP_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m meeting_recorder.cli "$@"
''')
        (package_root / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
        (package_root / "usr" / "share" / "applications" / f"{APP_ID}.desktop").write_text(desktop_file(f"/usr/bin/{COMMAND_NAME}"), encoding="utf-8")
        control_dir = package_root / "DEBIAN"
        control_dir.mkdir(parents=True, exist_ok=True)
        installed_size = max(1, sum(p.stat().st_size for p in package_root.rglob("*") if p.is_file()) // 1024)
        (control_dir / "control").write_text(f"""Package: {PACKAGE_NAME}\nVersion: {version}\nSection: utils\nPriority: optional\nArchitecture: all\nDepends: python3 (>= 3.10), python3-tk, ffmpeg\nInstalled-Size: {installed_size}\nMaintainer: Meeting Recorder Maintainers <noreply@example.invalid>\nDescription: Local-first Linux meeting recorder\n Records screen, audio, transcripts, and summaries into private local meeting folders.\n""", encoding="utf-8")
        env = os.environ.copy()
        env.setdefault("SOURCE_DATE_EPOCH", str(epoch))
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(package_root), str(asset)], check=True, env=env)
    return asset


def write_sha256sums(dist: Path, assets: Iterable[Path]) -> Path:
    sums = dist / "SHA256SUMS"
    lines = []
    for asset in sorted(assets, key=lambda p: p.name):
        h = hashlib.sha256(asset.read_bytes()).hexdigest()
        lines.append(f"{h}  {asset.name}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sums


def build_assets(root: Path | None = None, dist: Path | None = None, version: str | None = None, clean: bool = True) -> list[Path]:
    root = root or project_root()
    version = version or read_version(root)
    dist = dist or root / "dist"
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", DEFAULT_EPOCH))
    if clean and dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True, exist_ok=True)
    assets: list[Path] = [build_source_installer(root, dist, version, epoch)]
    deb = build_deb(root, dist, version, epoch)
    if deb is not None:
        assets.append(deb)
    assets.append(write_sha256sums(dist, assets))
    return assets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Meeting Recorder release assets")
    parser.add_argument("--root", type=Path, default=project_root())
    parser.add_argument("--dist", type=Path, default=None)
    parser.add_argument("--version", default=None)
    parser.add_argument("--no-clean", action="store_true", help="Do not remove the dist directory before building")
    args = parser.parse_args(argv)
    assets = build_assets(args.root.resolve(), args.dist.resolve() if args.dist else None, args.version, clean=not args.no_clean)
    for asset in assets:
        print(asset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
