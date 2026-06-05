from __future__ import annotations

import importlib.util
from pathlib import Path
import tarfile

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_release_assets.py"
_SPEC = importlib.util.spec_from_file_location("build_release_assets", _SCRIPT)
assert _SPEC and _SPEC.loader
build_release_assets = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_release_assets)

build_assets = build_release_assets.build_assets
is_excluded = build_release_assets.is_excluded
project_root = build_release_assets.project_root
read_version = build_release_assets.read_version


def test_release_source_installer_has_expected_files_and_excludes_caches(tmp_path):
    root = project_root()
    version = read_version(root)
    assets = build_assets(root=root, dist=tmp_path / "dist", version=version, clean=True)

    tarball = tmp_path / "dist" / f"meeting-recorder-app-{version}-linux-source-installer.tar.gz"
    sums = tmp_path / "dist" / "SHA256SUMS"
    assert tarball in assets
    assert tarball.exists()
    assert sums.exists()

    with tarfile.open(tarball, "r:gz") as tf:
        names = set(tf.getnames())

    prefix = f"meeting-recorder-app-{version}/"
    expected = {
        prefix + "install.sh",
        prefix + "uninstall.sh",
        prefix + "meeting-recorder.desktop",
        prefix + "meeting-recorder",
        prefix + "README.md",
        prefix + "CHANGELOG.md",
        prefix + "RELEASE.md",
        prefix + "pyproject.toml",
        prefix + "src/meeting_recorder/cli.py",
        prefix + "scripts/build_release_assets.py",
    }
    assert expected <= names

    forbidden_fragments = [
        "/.git/",
        "/.pytest_cache/",
        "/__pycache__/",
        "/build/",
        "/dist/",
        ".egg-info/",
        ".pyc",
        "/.venv/",
        "/Meetings/",
        "/docs/plans/",
    ]
    assert not any(any(fragment in name for fragment in forbidden_fragments) for name in names)


def test_release_builder_writes_checksums_for_assets(tmp_path):
    root = project_root()
    version = read_version(root)
    assets = build_assets(root=root, dist=tmp_path / "dist", version=version, clean=True)
    checksums = (tmp_path / "dist" / "SHA256SUMS").read_text(encoding="utf-8")

    asset_names = {asset.name for asset in assets if asset.name != "SHA256SUMS"}
    for name in asset_names:
        assert f"  {name}" in checksums
    assert "SHA256SUMS" not in checksums


def test_debian_package_contains_launcher_when_dpkg_deb_available(tmp_path):
    root = project_root()
    version = read_version(root)
    build_assets(root=root, dist=tmp_path / "dist", version=version, clean=True)
    deb = tmp_path / "dist" / f"meeting-recorder-app_{version}_all.deb"
    if not deb.exists():
        return

    import subprocess

    contents = subprocess.check_output(["dpkg-deb", "--contents", str(deb)], text=True)
    assert "/usr/bin/meeting-recorder" in contents
    assert "/usr/share/applications/meeting-recorder.desktop" in contents
    assert "-rw-r--r-- root/root" in contents
    assert "-rw------- root/root" not in contents
    assert "drwxrwxr-x root/root" not in contents
    info = subprocess.check_output(["dpkg-deb", "--info", str(deb)], text=True)
    assert f"Version: {version}" in info
    assert "Depends: python3 (>= 3.10), ffmpeg, chromium | electron" in info


def test_exclusion_rules_cover_private_and_generated_paths(tmp_path):
    root = tmp_path
    paths = [
        root / ".git" / "config",
        root / "build" / "x.py",
        root / "dist" / "asset.tar.gz",
        root / "src" / "pkg.egg-info" / "PKG-INFO",
        root / "src" / "meeting_recorder" / "__pycache__" / "cli.cpython-311.pyc",
        root / "Meetings" / "private" / "recording.mkv",
        root / "docs" / "plans" / "private-plan.md",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        assert is_excluded(path, root)
