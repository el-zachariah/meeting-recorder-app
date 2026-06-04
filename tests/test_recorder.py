import subprocess

import pytest

from meeting_recorder.recorder import build_ffmpeg_command, detect_screen_size, preflight_recording, start_recording, stop_recording


def test_detect_screen_size_uses_xdpyinfo(monkeypatch):
    monkeypatch.delenv("MEETING_RECORDER_SIZE", raising=False)
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/xdpyinfo" if name == "xdpyinfo" else None)

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="  dimensions:    2560x1440 pixels (677x381 millimeters)\n", stderr="")

    monkeypatch.setattr("meeting_recorder.recorder.subprocess.run", fake_run)
    assert detect_screen_size(":1") == "2560x1440"


def test_build_ffmpeg_command_preserves_arg_list_and_display(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr("meeting_recorder.recorder.detect_screen_size", lambda display=None: "1600x900")
    monkeypatch.setattr("meeting_recorder.recorder.detect_audio_inputs", lambda: {"pulse_monitor": "mon", "pulse_mic": "mic", "alsa_default": "default"})

    cmd = build_ffmpeg_command(tmp_path / "out.mkv", display=":2", include_system_audio=True, include_mic=False)

    assert isinstance(cmd, list)
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert ":2" in cmd
    assert "1600x900" in cmd
    assert "mon" in cmd
    assert "mic" not in cmd


def test_preflight_requires_ffmpeg(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        preflight_recording(display=":0")


def test_preflight_requires_display(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(RuntimeError, match="DISPLAY"):
        preflight_recording()


def test_start_recording_raises_when_ffmpeg_exits(monkeypatch, tmp_path):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr("meeting_recorder.recorder.build_ffmpeg_command", lambda output_file, **kwargs: ["ffmpeg", "fake"])

    class FakeProc:
        stdin = None
        def poll(self):
            return 1

    def fake_popen(args, **kwargs):
        kwargs["stderr"].write("display error")
        kwargs["stderr"].flush()
        return FakeProc()

    monkeypatch.setattr("meeting_recorder.recorder.subprocess.Popen", fake_popen)
    with pytest.raises(RuntimeError, match="display error"):
        start_recording(tmp_path / "out.mkv", readiness_timeout=0)


def test_stop_recording_sends_q_and_closes_log(tmp_path):
    writes = []

    class Stdin:
        def write(self, data):
            writes.append(data)
        def flush(self):
            pass

    class Proc:
        stdin = Stdin()
        waited = False
        def poll(self):
            return None if not self.waited else 0
        def wait(self, timeout=None):
            self.waited = True
            return 0

    log = (tmp_path / "ffmpeg.log").open("w", encoding="utf-8")
    from meeting_recorder.recorder import RecorderProcess
    recorder = RecorderProcess(Proc(), tmp_path / "out.mkv", ["ffmpeg"], tmp_path / "ffmpeg.log", log)

    stop_recording(recorder, timeout=1)

    assert writes == ["q\n"]
    assert log.closed
