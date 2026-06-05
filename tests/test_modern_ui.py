from __future__ import annotations

from urllib.request import Request, urlopen
import json

from meeting_recorder.modern_ui import ModernBridgeService, ModernGuiState, RecorderBridgeBackend, render_modern_ui_html


def test_modern_ui_contains_approved_visual_tokens():
    html = render_modern_ui_html(ModernGuiState(recording=True, elapsed_seconds=157, size_bytes=24_800_000))

    assert "Meeting Recorder" in html
    assert "main-popover" in html
    assert "save-panel" in html
    assert "linear-gradient(145deg,rgba(22,25,34,.91),rgba(14,17,25,.84))" in html
    assert "Recording..." in html
    assert "Save &amp; Transcribe" in html
    assert "Tk" not in html
    assert "ttk" not in html.lower()


def test_modern_runtime_starts_truthfully_idle_not_as_a_reference_screenshot():
    state = ModernGuiState()
    html = render_modern_ui_html(state, bridge_url="http://127.0.0.1:9")

    assert state.recording is False
    assert state.elapsed_seconds == 0
    assert state.size_bytes == 0
    assert "00:02:37" not in html
    assert "24.8 MB" not in html
    assert "Team Sync – May 20, 2025" not in html
    assert "data-action=\"start\"" in html
    assert "Start" in html


def test_modern_ui_visible_controls_are_real_form_or_action_controls():
    html = render_modern_ui_html(ModernGuiState(), bridge_url="http://127.0.0.1:9")

    assert 'id="session-title"' in html
    assert '<input' in html
    assert 'id="microphone"' in html
    assert '<select' in html
    assert 'id="system-audio"' in html and 'type="checkbox"' in html
    assert 'id="record-area"' in html
    assert 'id="show-clicks"' in html
    assert 'id="countdown"' in html
    assert 'id="save-dir"' in html
    assert 'data-action="choose-folder"' in html
    assert "async function loadState" in html
    assert "renderState(payload.state" in html
    assert "document.getElementById('save-panel').hidden = !(state.saving || state.transcribing || state.saved || state.meeting_path);" in html


def test_modern_bridge_state_and_actions(tmp_path):
    bridge = ModernBridgeService(tmp_path).start()
    try:
        with urlopen(bridge.url + "/state", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["state"]["recording"] is False

        req = Request(
            bridge.url + "/action/start",
            data=json.dumps({"meeting_title": "Real title", "save_dir": str(tmp_path / "custom"), "system_audio": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["state"]["recording"] is True
        assert payload["state"]["meeting_title"] == "Real title"
        assert payload["state"]["save_dir"].endswith("custom")
        assert payload["state"]["system_audio"] is False

        req = Request(bridge.url + "/action/pause", method="POST")
        with urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["state"]["paused"] is True
    finally:
        bridge.stop()


def test_backend_dispatch_updates_canonical_bridge_state(tmp_path):
    class Backend:
        def __init__(self):
            self.calls = []

        def configure(self, state):
            self.calls.append(("configure", state.meeting_title, state.save_dir, state.system_audio))

        def start(self):
            self.calls.append("start")
            return {"recording": True, "raw_file": "/tmp/live.mka"}

        def pause(self):
            self.calls.append("pause")
            return {"paused": True}

        def stop(self):
            self.calls.append("stop")
            return {"recording": False, "meeting_path": str(tmp_path / "saved")}

    backend = Backend()
    bridge = ModernBridgeService(tmp_path, backend=backend).start()
    try:
        for action in ["start", "pause", "stop"]:
            req = Request(bridge.url + f"/action/{action}", method="POST")
            with urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["ok"] is True

        assert [call for call in backend.calls if isinstance(call, str)] == ["start", "pause", "stop"]
        configure_calls = [call for call in backend.calls if isinstance(call, tuple)]
        assert len(configure_calls) == 3
        assert all(call[0] == "configure" and call[3] is True for call in configure_calls)
        with urlopen(bridge.url + "/state", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["state"]["recording"] is False
        assert payload["state"]["paused"] is False
        assert payload["state"]["meeting_path"].endswith("saved")
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
    backend.configure(ModernGuiState(meeting_title="Custom meeting", save_dir=str(tmp_path / "Chosen"), system_audio=False, record_area="Audio only"))
    result = backend.start()
    assert result["recording"] is True
    assert started and started[0][0].suffix in {".mka", ".mkv"}
    assert started[0][1]["include_system_audio"] is False
    assert started[0][1]["include_video"] is False

    result = backend.stop()
    assert result["recording"] is False
    assert (tmp_path / "Chosen").exists()
    assert result["media_path"].endswith(("recording.mka", "recording.mkv"))
