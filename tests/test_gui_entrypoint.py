from __future__ import annotations

from pathlib import Path

import pytest

from meeting_recorder import gui
from meeting_recorder.tray import TrayBackendUnavailable


class FakeRoot:
    def __init__(self):
        self.mainloop_called = False
        self.destroy_called = False
        self.withdraw_called = False

    def withdraw(self):
        self.withdraw_called = True

    def mainloop(self):
        self.mainloop_called = True

    def destroy(self):
        self.destroy_called = True


def test_gui_main_launches_native_system_tray_not_webview(monkeypatch, tmp_path):
    root = FakeRoot()
    launched = []

    def fake_tray_app(root_arg, default_dir):
        launched.append((root_arg, default_dir))

    def fail_webview(default_dir):  # pragma: no cover - only used on regression
        raise AssertionError("meeting-recorder gui must not bypass the native system tray")

    monkeypatch.setattr(gui.tk, "Tk", lambda: root)
    monkeypatch.setattr(gui, "SystemTrayDropdownGUI", fake_tray_app)
    monkeypatch.setattr("meeting_recorder.modern_ui.launch_modern_gui", fail_webview)

    gui.main(tmp_path / "Meetings")

    assert launched == [(root, tmp_path / "Meetings")]
    assert root.mainloop_called is True
    assert root.destroy_called is False


def test_gui_main_missing_tray_backend_is_actionable(monkeypatch, tmp_path, capsys):
    root = FakeRoot()

    def missing_tray(root_arg, default_dir):
        raise TrayBackendUnavailable("System tray backend unavailable; install pystray/Pillow/AppIndicator dependencies")

    monkeypatch.setattr(gui.tk, "Tk", lambda: root)
    monkeypatch.setattr(gui, "SystemTrayDropdownGUI", missing_tray)

    with pytest.raises(SystemExit) as exc:
        gui.main(tmp_path / "Meetings")

    assert exc.value.code == 2
    assert root.destroy_called is True
    assert "System tray backend unavailable" in capsys.readouterr().err
