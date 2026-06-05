from __future__ import annotations

from urllib.request import Request, urlopen
import json

from meeting_recorder.modern_ui import ModernBridgeService, ModernGuiState, RecorderBridgeBackend, render_modern_ui_html


def test_modern_ui_contains_approved_visual_tokens():
    html = render_modern_ui_html(ModernGuiState())

    assert "Meeting Recorder" in html
    assert "main-popover" in html
    assert "save-panel" in html
    assert "linear-gradient(145deg,rgba(22,25,34,.91),rgba(14,17,25,.84))" in html
    assert "Recording..." in html
    assert "Save &amp; Transcribe" in html
    assert "Tk" not in html
    assert "ttk" not in html.lower()


def test_modern_bridge_state_and_actions(tmp_path):
    bridge = ModernBridgeService(tmp_path).start()
    try:
        with urlopen(bridge.url + "/state", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["state"]["recording"] is True

        req = Request(bridge.url + "/action/pause", method="POST")
        with urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["state"]["paused"] is True
    finally:
        bridge.stop()


def test_recorder_bridge_backend_uses_existing_recorder_path(monkeypatch, tmp_path):
    class Proc:
        def poll(self):
            return None

    class Recorder:
        process = Proc()
        paused = False

    started = []

    def fake_start(path, **kwargs):
        started.append((path, kwargs))
        return Recorder()

    def fake_stop(recorder):
        started[0][0].write_bytes(b"media")

    monkeypatch.setattr("meeting_recorder.recorder.start_recording", fake_start)
    monkeypatch.setattr("meeting_recorder.recorder.stop_recording", fake_stop)

    backend = RecorderBridgeBackend(tmp_path / "Meetings")
    result = backend.start()
    assert result["recording"] is True
    assert started and started[0][0].suffix in {".mka", ".mkv"}

    result = backend.stop()
    assert result["recording"] is False
    assert (tmp_path / "Meetings").exists()
    assert result["media_path"].endswith(("recording.mka", "recording.mkv"))
