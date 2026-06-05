import sys
import types

import pytest

from meeting_recorder.tray import TrayBackendUnavailable, create_tray_icon, require_tray_backend


class FakeRoot:
    def __init__(self):
        self.calls = []

    def after(self, delay, callback):
        self.calls.append((delay, callback))
        callback()


class FakeApp:
    def __init__(self):
        self.root = FakeRoot()
        self.opened = False
        self.recording_toggled = False
        self.closed = False

    def show_tray_dropdown(self):
        self.opened = True

    def toggle_recording(self):
        self.recording_toggled = True

    def shutdown(self):
        self.closed = True


def test_require_tray_backend_rejects_missing_pystray(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)

    with pytest.raises(TrayBackendUnavailable) as exc:
        require_tray_backend()

    assert "system tray" in str(exc.value)
    assert "python3-pystray" in str(exc.value)


def test_create_tray_icon_uses_native_tray_menu_without_corner_window(monkeypatch):
    created = {}

    class FakeMenuItem:
        def __init__(self, text, action, default=False):
            self.text = text
            self.action = action
            self.default = default

    class FakeMenu(tuple):
        def __new__(cls, *items):
            return super().__new__(cls, items)

    class FakeIcon:
        def __init__(self, name, image, title, menu):
            created["name"] = name
            created["image"] = image
            created["title"] = title
            created["menu"] = menu
            self.visible = False
            self.stopped = False

        def run_detached(self):
            self.visible = True

        def stop(self):
            self.stopped = True

    fake_pystray = types.SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)

    class FakeImage:
        @staticmethod
        def new(mode, size, color):
            return {"mode": mode, "size": size, "color": color}

    class FakeDraw:
        def ellipse(self, *_args, **_kwargs):
            pass

    fake_pil_image = types.SimpleNamespace(new=FakeImage.new)
    fake_pil_draw = types.SimpleNamespace(Draw=lambda _image: FakeDraw())
    monkeypatch.setitem(sys.modules, "pystray", fake_pystray)
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(Image=fake_pil_image, ImageDraw=fake_pil_draw))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)
    monkeypatch.setitem(sys.modules, "PIL.ImageDraw", fake_pil_draw)

    app = FakeApp()
    icon = create_tray_icon(app)

    assert created["name"] == "meeting-recorder"
    assert created["title"] == "Meeting Recorder"
    menu_labels = [item.text for item in created["menu"]]
    assert menu_labels == ["Open Meeting Recorder", "Start / Stop Recording", "Quit"]
    assert created["menu"][0].default is True

    created["menu"][0].action(icon, created["menu"][0])
    assert app.opened is True
    created["menu"][1].action(icon, created["menu"][1])
    assert app.recording_toggled is True
    created["menu"][2].action(icon, created["menu"][2])
    assert app.closed is True
