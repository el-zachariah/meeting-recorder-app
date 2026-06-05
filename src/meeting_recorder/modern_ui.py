from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Any
from urllib.parse import urlparse

from .settings import load_settings

APP_WIDTH = 1672
APP_HEIGHT = 941
WAVE_HEIGHTS = [3,8,27,15,5,15,25,8,5,22,31,67,27,7,17,9,2,4,2,6,18,34,9,5,8,28,64,39,24,58,16,7,6,7,5,5,16,3,13,8,4,51,70,24,34,9,8,5,3,13,54,36,72,21,7,5,4,3,2,12,44,72,21,53,16,4]


@dataclass
class ModernGuiState:
    recording: bool = True
    paused: bool = False
    elapsed: str = "00:02:37"
    size: str = "24.8 MB"
    meeting_title: str = "Team Sync – May 20, 2025"
    save_dir: str = "~/Videos/Recordings"
    microphone: str = "Internal Microphone"
    system_audio: bool = True
    record_area: str = "Full screen"
    show_clicks: bool = True
    countdown: str = "3 seconds"
    saving: bool = True
    transcribing: bool = True


def default_state(default_dir: Path | None = None) -> ModernGuiState:
    settings = load_settings()
    save_dir = settings.default_save_location or str(default_dir or Path.home() / "Videos" / "Recordings")
    state = ModernGuiState(save_dir=_display_path(Path(save_dir).expanduser()))
    state.system_audio = bool(settings.record_system_audio)
    return state


def _display_path(path: Path) -> str:
    try:
        return "~" + str(path).removeprefix(str(Path.home())) if str(path).startswith(str(Path.home())) else str(path)
    except Exception:
        return str(path)


def render_modern_ui_html(state: ModernGuiState | None = None, *, bridge_url: str | None = None) -> str:
    state = state or ModernGuiState()
    rec_label = "Paused" if state.paused else ("Recording..." if state.recording else "Ready")
    body_class = "is-recording" if state.recording else "is-ready"
    bridge_script = f"window.MEETING_RECORDER_BRIDGE = {json.dumps(bridge_url)};" if bridge_url else "window.MEETING_RECORDER_BRIDGE = null;"
    bars = "".join(f'<i class="bar {"dotbar" if h < 6 else ""}" style="height:{h}px"></i>' for h in WAVE_HEIGHTS)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Meeting Recorder</title>
<style>
  :root{{
    --bg0:#121724; --bg1:#263147; --bg2:#10131b;
    --panel:rgba(17,20,29,.82); --panel2:rgba(24,28,39,.78);
    --stroke:rgba(170,185,215,.18); --stroke2:rgba(255,255,255,.10);
    --text:#f4f7fb; --muted:#a7b0c2; --muted2:#7f899c;
    --red:#ff4e5d; --red2:#c5222d; --blue:#2478ff; --green:#62d282;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;width:{APP_WIDTH}px;height:{APP_HEIGHT}px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Inter","SF Pro Display","Segoe UI",system-ui,sans-serif;color:var(--text);background:#0d1018;}}
  button{{font:inherit;color:inherit;border:0;padding:0;cursor:pointer}}
  .wallpaper{{position:absolute;inset:0;background:
    radial-gradient(800px 480px at 18% 87%, rgba(202,119,65,.62), transparent 65%),
    radial-gradient(850px 520px at 80% 28%, rgba(70,93,134,.72), transparent 70%),
    radial-gradient(1200px 720px at 42% 52%, rgba(84,100,133,.72), transparent 75%),
    linear-gradient(135deg,#171b28 0%,#30394f 42%,#0c0f16 100%);filter:saturate(.95);}}
  .wallpaper:after{{content:"";position:absolute;inset:0;background:rgba(7,9,14,.36);backdrop-filter:blur(8px)}}
  .topbar{{position:absolute;top:0;left:0;right:0;height:68px;background:rgba(9,12,19,.64);backdrop-filter:blur(24px) saturate(1.25);box-shadow:0 1px 0 rgba(255,255,255,.06),0 18px 40px rgba(0,0,0,.22);display:flex;align-items:center;justify-content:center;gap:42px;font-size:24px;color:#e8edf7;letter-spacing:.01em;}}
  .topbar .icons{{display:flex;gap:42px;align-items:center}}.icon{{width:34px;height:34px;display:grid;place-items:center;color:#dce4f1}}.date{{font-size:24px;min-width:250px}}.tray{{width:68px;height:56px;border-radius:12px;border:1px solid rgba(77,143,255,.72);background:linear-gradient(180deg,rgba(45,57,82,.95),rgba(31,37,52,.85));box-shadow:0 0 0 1px rgba(31,119,255,.45),0 9px 28px rgba(0,0,0,.35),inset 0 1px rgba(255,255,255,.12);display:grid;place-items:center;position:relative}}.tray:before{{content:"";width:30px;height:30px;border-radius:50%;border:3px solid #ff8c9a;box-shadow:inset 0 0 0 8px #1c2230;background:#ff4053}}.tray:after{{content:"";position:absolute;bottom:-31px;border-left:22px solid transparent;border-right:22px solid transparent;border-bottom:22px solid rgba(16,19,28,.88);filter:drop-shadow(0 -1px 0 rgba(255,255,255,.12));}}
  .main-popover{{position:absolute;top:88px;left:315px;width:710px;height:800px;border-radius:24px;background:linear-gradient(145deg,rgba(22,25,34,.91),rgba(14,17,25,.84));backdrop-filter:blur(28px) saturate(1.35);border:1px solid var(--stroke);box-shadow:0 36px 90px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.08);padding:34px 36px;}}
  .head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}}.title{{font-size:29px;font-weight:760;letter-spacing:-.025em}}.head-actions{{display:flex;gap:26px;color:#c5cee0}}.head-actions span{{font-size:30px;opacity:.9}}
  .status-row{{display:flex;align-items:center;gap:30px;margin-bottom:24px;font-size:24px}}.rec-dot{{width:25px;height:25px;border-radius:50%;border:3px solid var(--red);box-shadow:inset 0 0 0 5px rgba(255,78,93,.22)}}.rec-label{{color:var(--red);font-weight:650}}.timer{{font-variant-numeric:tabular-nums;font-weight:570;letter-spacing:.03em}}.size{{margin-left:auto;color:#bac4d5;font-size:21px;display:flex;gap:12px;align-items:center}}
  .wave{{height:75px;display:flex;align-items:center;gap:5px;margin:6px 0 25px}}.bar{{width:4px;border-radius:6px;background:linear-gradient(#ff9ca8,#ff5362);opacity:.95;box-shadow:0 0 10px rgba(255,74,92,.2)}}.dotbar{{height:3px;opacity:.45}}
  .controls{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:22px;margin-bottom:18px}}.control{{height:120px;border-radius:18px;border:1px solid var(--stroke2);background:linear-gradient(180deg,rgba(43,48,63,.68),rgba(19,22,31,.72));display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;font-size:19px;box-shadow:inset 0 1px rgba(255,255,255,.06),0 8px 20px rgba(0,0,0,.16)}}.control .glyph{{height:32px;color:#f3f6fb}}.control.stop{{background:linear-gradient(180deg,#e2414c,#c32631);border-color:rgba(255,115,125,.38);box-shadow:0 16px 40px rgba(198,38,49,.32), inset 0 1px rgba(255,255,255,.18)}}
  .settings{{height:388px;border-radius:15px;border:1px solid var(--stroke2);background:linear-gradient(180deg,rgba(31,35,47,.55),rgba(18,21,30,.44));padding:17px 20px}}.settings-title{{color:var(--muted);font-size:18px;margin-bottom:13px}}.row{{height:53px;display:grid;grid-template-columns:32px 1fr 318px;align-items:center;gap:14px;font-size:20px;color:#dfe5ef}}.row span{{font-size:25px;color:#d1d9e7}}.select,.path{{height:45px;border-radius:10px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(180deg,rgba(45,50,63,.72),rgba(29,33,44,.72));display:flex;align-items:center;justify-content:space-between;padding:0 14px;color:#ccd5e4;box-shadow:inset 0 1px rgba(255,255,255,.05)}}.switch{{justify-self:end;width:62px;height:34px;border-radius:99px;background:#287fff;padding:3px;box-shadow:inset 0 1px rgba(255,255,255,.22),0 6px 16px rgba(36,120,255,.28)}}.switch:after{{content:"";display:block;margin-left:auto;width:28px;height:28px;border-radius:50%;background:#f7fbff;box-shadow:0 3px 8px rgba(0,0,0,.3)}}.path{{justify-content:flex-start;gap:10px}}.folder-btn{{margin-left:auto;width:52px;height:45px;border-left:1px solid rgba(255,255,255,.09);display:grid;place-items:center;color:#dce5f2}}
  .save-panel{{position:absolute;top:252px;left:1063px;width:504px;height:576px;border-radius:23px;background:linear-gradient(145deg,rgba(23,26,36,.91),rgba(15,18,26,.82));border:1px solid var(--stroke);box-shadow:0 34px 80px rgba(0,0,0,.4), inset 0 1px rgba(255,255,255,.08);backdrop-filter:blur(28px) saturate(1.35);padding:34px 36px}}.save-head{{display:flex;align-items:center;gap:22px;font-size:23px;margin-bottom:34px}}.label{{font-size:21px;color:#cbd3e2;margin-bottom:10px}}.input{{height:51px;border-radius:8px;border:1px solid rgba(58,145,255,.95);box-shadow:0 0 0 1px rgba(28,116,255,.25), inset 0 1px rgba(255,255,255,.06);background:rgba(19,23,32,.74);display:flex;align-items:center;padding:0 16px;font-size:22px;color:#eef3fb;margin-bottom:25px}}.primary{{height:54px;border-radius:9px;background:linear-gradient(180deg,#2d8cff,#1e68d6);display:flex;align-items:center;justify-content:center;gap:16px;font-size:22px;font-weight:660;box-shadow:0 13px 28px rgba(32,112,226,.32);margin-bottom:27px}}.divider{{height:1px;background:rgba(255,255,255,.12);margin-bottom:30px}}.progress{{display:grid;grid-template-columns:50px 1fr 34px;gap:0 0}}.rail{{grid-row:1/4;display:flex;flex-direction:column;align-items:center}}.node{{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#236fd6;font-size:20px}}.node.mid{{margin-top:50px;background:#192133;border:4px solid #2f74d6}}.node.done{{margin-top:55px;background:#62c779;color:#102316}}.line{{width:2px;height:49px;background:rgba(145,160,184,.45)}}.step{{height:83px}}.step-title{{font-size:19px;font-weight:650;margin-top:1px}}.step-sub{{font-size:17px;color:var(--muted);margin-top:7px}}.check{{color:#4fe07c;font-size:26px}}.spinner{{width:26px;height:26px;border:3px solid rgba(160,170,190,.25);border-top-color:#9da8ba;border-radius:50%}}.external{{color:#b9c2d2;font-size:26px}}.link{{color:#3993ff;margin-top:8px;font-size:18px}}
</style>
</head><body class="{body_class}">
<div class="wallpaper"></div>
<div class="topbar">
  <div class="icons"><div class="icon">☼</div><div class="icon">⌁</div><div class="icon">♬</div><div class="icon">▭</div></div>
  <div class="tray"></div>
  <div class="date">Tue May 20&nbsp;&nbsp; 10:42 AM</div>
</div>
<section class="main-popover">
  <div class="head"><div class="title">Meeting Recorder</div><div class="head-actions"><span>⚙</span><span>⋮</span></div></div>
  <div class="status-row"><div class="rec-dot"></div><div class="rec-label">{rec_label}</div><div class="timer">{state.elapsed}</div><div class="size">⌁ {state.size}</div></div>
  <div class="wave" aria-label="waveform">{bars}</div>
  <div class="controls"><button class="control" data-action="pause"><div class="glyph" style="font-size:38px">Ⅱ</div><div>Pause</div></button><button class="control stop" data-action="stop"><div class="glyph" style="font-size:37px">■</div><div>Stop</div></button><button class="control" data-action="resume"><div class="glyph" style="font-size:42px">◎</div><div>Resume</div></button></div>
  <div class="settings"><div class="settings-title">Settings</div>
    <div class="row"><span>♬</span><div>Microphone</div><div class="select">{state.microphone} <span>⌄</span></div></div>
    <div class="row"><span>▭</span><div>System audio</div><div class="switch"></div></div>
    <div class="row"><span>□</span><div>Record area</div><div class="select">{state.record_area} <span>⌄</span></div></div>
    <div class="row"><span>⌖</span><div>Show mouse clicks</div><div class="switch"></div></div>
    <div class="row"><span>◷</span><div>Countdown</div><div class="select">{state.countdown} <span>⌄</span></div></div>
    <div class="row"><span>▱</span><div>Save to</div><div class="path">{state.save_dir} <span class="folder-btn">▣</span></div></div>
  </div>
</section>
<section class="save-panel">
  <div class="save-head"><span style="font-size:34px">‹</span><span>Save Recording</span></div>
  <div class="label">Session name</div><div class="input">{state.meeting_title}</div><button class="primary" data-action="save">✦ Save &amp; Transcribe</button><div class="divider"></div>
  <div class="progress"><div class="rail"><div class="node">✓</div><div class="line"></div><div class="node mid"></div><div class="line"></div><div class="node done">✓</div></div>
    <div class="step"><div class="step-title">Saving recording...</div><div class="step-sub">Recording saved to {state.save_dir}</div></div><div class="check">✓</div>
    <div class="step"><div class="step-title">Transcribing audio...</div><div class="step-sub">This may take a few moments</div></div><div class="spinner"></div>
    <div class="step"><div class="step-title">Transcript saved locally</div><div class="link">Open transcript</div></div><div class="external">↗</div>
  </div>
</section>
<script>
{bridge_script}
async function bridge(action) {{
  if (!window.MEETING_RECORDER_BRIDGE) return;
  await fetch(window.MEETING_RECORDER_BRIDGE + '/action/' + action, {{method:'POST'}}).catch(() => null);
}}
document.querySelectorAll('[data-action]').forEach(el => el.addEventListener('click', () => bridge(el.dataset.action)));
</script>
</body></html>'''


def write_modern_ui_html(path: Path, state: ModernGuiState | None = None, *, bridge_url: str | None = None) -> Path:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_modern_ui_html(state, bridge_url=bridge_url), encoding="utf-8")
    return path


def _browser_candidates() -> list[str]:
    env = os.environ.get("MEETING_RECORDER_BROWSER")
    names = [env] if env else []
    names += ["electron", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge"]
    found: list[str] = []
    for name in names:
        if not name:
            continue
        path = shutil.which(name)
        if path and path not in found:
            found.append(path)
    return found


def _is_electron(executable: str) -> bool:
    return Path(executable).name.lower().startswith("electron")


def capture_modern_gui_screenshot(default_dir: Path, output_path: Path) -> Path:
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="meeting-recorder-ui-") as td:
        # Release evidence must match the approved visual direction exactly, not
        # drift with a developer's persisted settings/default output folder.
        html = write_modern_ui_html(Path(td) / "meeting-recorder-modern.html", ModernGuiState())
        last_error: Exception | None = None
        for browser in _browser_candidates():
            if _is_electron(browser):
                continue
            cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox", f"--window-size={APP_WIDTH},{APP_HEIGHT}", f"--screenshot={output_path}", html.as_uri()]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
            except Exception as exc:  # pragma: no cover - exercised in release smoke
                last_error = exc
        raise RuntimeError(f"No Chromium-compatible browser could render the modern GUI screenshot. Tried: {_browser_candidates()}. Last error: {last_error}")


class ModernBridgeService:
    """Small stdlib JSON bridge for the WebView/Electron-style frontend.

    The service exposes /state and /action/<name>. Actions are intentionally thin
    and call a backend adapter, so tests can verify wiring without starting real
    ffmpeg. Production can pass the recorder controller later without changing
    the frontend contract.
    """

    def __init__(self, default_dir: Path, backend: Any | None = None):
        self.default_dir = Path(default_dir)
        self.backend = backend
        self.state = default_state(default_dir)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        if not self._server:
            raise RuntimeError("bridge service is not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> "ModernBridgeService":
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload, default=str).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/state":
                    self._json(200, {"ok": True, "state": asdict(service.state), "now": datetime.now().isoformat(timespec="seconds")})
                    return
                self._json(404, {"ok": False, "error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                action = urlparse(self.path).path.removeprefix("/action/")
                if action not in {"start", "pause", "resume", "stop", "save"}:
                    self._json(404, {"ok": False, "error": "unknown action"})
                    return
                result = service.dispatch(action)
                self._json(200 if result.get("ok", False) else 500, result)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def dispatch(self, action: str) -> dict[str, Any]:
        if self.backend and hasattr(self.backend, action):
            try:
                value = getattr(self.backend, action)()
            except Exception as exc:
                return {"ok": False, "action": action, "error": str(exc)}
            return {"ok": True, "action": action, "result": value}
        if action == "start":
            self.state.recording = True
            self.state.paused = False
        elif action == "pause":
            self.state.paused = True
        elif action == "resume":
            self.state.recording = True
            self.state.paused = False
        elif action in {"stop", "save"}:
            self.state.recording = False
            self.state.paused = False
        return {"ok": True, "action": action, "state": asdict(self.state)}


class RecorderBridgeBackend:
    """Adapter from modern UI actions to the existing Python recorder backend."""

    def __init__(self, default_dir: Path):
        self.default_dir = Path(default_dir)
        self.recorder: Any | None = None
        self.raw_file: Path | None = None

    def start(self) -> dict[str, Any]:
        if self.recorder and self.recorder.process.poll() is None:
            return {"recording": True, "raw_file": str(self.raw_file)}
        from .recorder import start_recording

        settings = load_settings()
        raw_dir = Path(tempfile.mkdtemp(prefix="meeting-recorder-modern-raw-"))
        raw_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(raw_dir, 0o700)
        ext = "mkv" if settings.record_video else "mka"
        self.raw_file = raw_dir / f"modern-gui-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"
        self.recorder = start_recording(
            self.raw_file,
            fps=settings.fps,
            size=settings.size or None,
            include_system_audio=bool(settings.record_system_audio),
            include_mic=bool(settings.record_microphone),
            include_video=bool(settings.record_video),
        )
        return {"recording": True, "raw_file": str(self.raw_file)}

    def pause(self) -> dict[str, Any]:
        if self.recorder and self.recorder.process.poll() is None:
            from .recorder import pause_recording

            pause_recording(self.recorder)
        return {"paused": bool(self.recorder and getattr(self.recorder, "paused", False))}

    def resume(self) -> dict[str, Any]:
        if self.recorder and self.recorder.process.poll() is None:
            from .recorder import resume_recording

            resume_recording(self.recorder)
        return {"paused": bool(self.recorder and getattr(self.recorder, "paused", False))}

    def stop(self) -> dict[str, Any]:
        if not self.recorder or not self.raw_file:
            return {"recording": False, "meeting_path": None}
        from .organizer import organize_recording
        from .recorder import resume_recording, stop_recording

        if getattr(self.recorder, "paused", False):
            resume_recording(self.recorder)
        stop_recording(self.recorder)
        if not self.raw_file.exists() or self.raw_file.stat().st_size == 0:
            return {"recording": False, "error": "Recording stopped but no output was produced", "raw_file": str(self.raw_file)}
        meeting = organize_recording(
            self.raw_file,
            self.default_dir,
            f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            metadata={"capture": "ffmpeg local capture from modern WebView UI"},
        )
        try:
            self.raw_file.parent.rmdir()
        except OSError:
            pass
        self.recorder = None
        self.raw_file = None
        return {"recording": False, "meeting_path": str(meeting.path), "media_path": str(meeting.media_path)}

    def save(self) -> dict[str, Any]:
        return self.stop()


def launch_modern_gui(default_dir: Path) -> int:
    bridge = ModernBridgeService(default_dir, backend=RecorderBridgeBackend(default_dir)).start()
    with tempfile.TemporaryDirectory(prefix="meeting-recorder-ui-") as td:
        html = write_modern_ui_html(Path(td) / "meeting-recorder-modern.html", default_state(default_dir), bridge_url=bridge.url)
        browser = _browser_candidates()[0] if _browser_candidates() else None
        if not browser:
            bridge.stop()
            raise RuntimeError("No Electron/Chromium-compatible runtime found. Install Electron or Chromium to launch the modern GUI.")
        if _is_electron(browser):
            cmd = [browser, "--no-sandbox", html.as_uri()]
        else:
            cmd = [browser, "--app=" + html.as_uri(), f"--window-size={APP_WIDTH},{APP_HEIGHT}"]
        try:
            return subprocess.call(cmd)
        finally:
            bridge.stop()
