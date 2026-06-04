import subprocess

import pytest

from meeting_recorder.recorder import (
    AudioDetection,
    AudioSource,
    build_ffmpeg_command,
    detect_audio_sources,
    detect_screen_size,
    parse_ffmpeg_pulse_sources,
    preflight_recording,
    start_recording,
    stop_recording,
)


def test_detect_screen_size_uses_xdpyinfo(monkeypatch):
    monkeypatch.delenv("MEETING_RECORDER_SIZE", raising=False)
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/xdpyinfo" if name == "xdpyinfo" else None)

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="  dimensions:    2560x1440 pixels (677x381 millimeters)\n", stderr="")

    monkeypatch.setattr("meeting_recorder.recorder.subprocess.run", fake_run)
    assert detect_screen_size(":1") == "2560x1440"


def test_parse_ffmpeg_pulse_sources_finds_monitor():
    output = """Auto-detected sources for pulse:
* auto_null.monitor [Monitor of Dummy Output] (none)
  alsa_input.usb-mic [USB Mic] (none)
"""
    sources = parse_ffmpeg_pulse_sources(output)
    assert sources[0].name == "auto_null.monitor"
    assert sources[0].kind == "system"
    assert sources[1].kind == "mic"


def test_detect_audio_sources_prefers_default_sink_monitor(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/pactl" if name == "pactl" else "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr(
        "meeting_recorder.recorder._pactl_sources",
        lambda pactl: [("alsa_output.hdmi.monitor", None), ("alsa_output.analog.monitor", None), ("alsa_input.usb", None)],
    )
    monkeypatch.setattr("meeting_recorder.recorder._pactl_default_sink", lambda pactl: "alsa_output.analog")
    detection = detect_audio_sources()
    assert detection.selected_system is not None
    assert detection.selected_system.name == "alsa_output.analog.monitor"
    assert detection.selected_system.is_default is True


def test_build_ffmpeg_command_audio_only_blocks_missing_system_audio(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr("meeting_recorder.recorder.detect_audio_sources", lambda: AudioDetection())
    with pytest.raises(RuntimeError, match="System audio"):
        build_ffmpeg_command(tmp_path / "out.mka", include_video=False, include_system_audio=True)


def test_detect_audio_sources_falls_back_to_ffmpeg_when_pactl_missing(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)

    def fake_run(args, **kwargs):
        assert args == ["/usr/bin/ffmpeg", "-hide_banner", "-sources", "pulse"]
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="* app.monitor [Monitor]\n  mic [Mic]\n")

    monkeypatch.setattr("meeting_recorder.recorder.subprocess.run", fake_run)
    detection = detect_audio_sources()
    assert detection.selected_system is not None
    assert detection.selected_system.name == "app.monitor"
    assert detection.selected_mic is not None
    assert detection.selected_mic.name == "mic"


def test_build_ffmpeg_command_audio_only_no_x11grab(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr(
        "meeting_recorder.recorder.detect_audio_sources",
        lambda: AudioDetection(selected_system=AudioSource("mon", "system"), system_sources=[AudioSource("mon", "system")]),
    )
    cmd = build_ffmpeg_command(tmp_path / "out.mka", include_video=False, include_system_audio=True, include_mic=False)
    assert "x11grab" not in cmd
    assert "-vn" in cmd
    assert "mon" in cmd
    assert "0:a" in cmd


def test_build_ffmpeg_command_audio_only_system_and_mic_uses_amix(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr(
        "meeting_recorder.recorder.detect_audio_sources",
        lambda: AudioDetection(
            selected_system=AudioSource("mon", "system"),
            selected_mic=AudioSource("mic", "mic"),
            system_sources=[AudioSource("mon", "system")],
            mic_sources=[AudioSource("mic", "mic")],
        ),
    )
    cmd = build_ffmpeg_command(tmp_path / "out.mka", include_video=False, include_system_audio=True, include_mic=True)
    joined = " ".join(cmd)
    assert "amix=inputs=2" in joined
    assert "[0:a][1:a]" in joined
    assert "-vn" in cmd


def test_build_ffmpeg_command_video_maps_indexes(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr("meeting_recorder.recorder.detect_screen_size", lambda display=None: "1600x900")
    monkeypatch.setattr(
        "meeting_recorder.recorder.detect_audio_sources",
        lambda: AudioDetection(selected_system=AudioSource("mon", "system"), system_sources=[AudioSource("mon", "system")]),
    )
    cmd = build_ffmpeg_command(tmp_path / "out.mkv", display=":2", include_video=True, include_system_audio=True, include_mic=False)
    joined = " ".join(cmd)
    assert "x11grab" in cmd
    assert ":2" in cmd
    assert "1600x900" in cmd
    assert "-map 0:v" in joined
    assert "-map 1:a" in joined


def test_build_ffmpeg_command_rejects_no_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr("meeting_recorder.recorder.detect_audio_sources", lambda: AudioDetection())
    with pytest.raises(RuntimeError, match="No recordable inputs"):
        build_ffmpeg_command(tmp_path / "out.mka", include_video=False, include_system_audio=False, include_mic=True)


def test_preflight_requires_ffmpeg(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        preflight_recording(display=":0", include_system_audio=False)


def test_preflight_video_requires_display(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(RuntimeError, match="DISPLAY"):
        preflight_recording(include_video=True, include_system_audio=False)


def test_preflight_audio_only_does_not_require_display(monkeypatch):
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(
        "meeting_recorder.recorder.detect_audio_sources",
        lambda: AudioDetection(selected_system=AudioSource("mon", "system"), system_sources=[AudioSource("mon", "system")]),
    )
    preflight_recording(include_video=False, include_system_audio=True)


def test_start_recording_raises_when_ffmpeg_exits(monkeypatch, tmp_path):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr("meeting_recorder.recorder.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr("meeting_recorder.recorder.detect_audio_sources", lambda: AudioDetection())
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
        start_recording(tmp_path / "out.mkv", readiness_timeout=0, include_system_audio=False, include_video=True)


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
