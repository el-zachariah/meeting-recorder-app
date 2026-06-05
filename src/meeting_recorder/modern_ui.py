from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html as html_lib
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
    recording: bool = False
    paused: bool = False
    elapsed_seconds: int = 0
    size_bytes: int = 0
    meeting_title: str = "Untitled meeting"
    save_dir: str = "~/Videos/Recordings"
    microphone: str = "Default microphone"
    system_audio: bool = True
    record_area: str = "Full screen"
    show_clicks: bool = True
    countdown: str = "3 seconds"
    saving: bool = False
    transcribing: bool = False
    saved: bool = False
    error: str = ""
    meeting_path: str | None = None
    media_path: str | None = None
    transcript_path: str | None = None


def default_state(default_dir: Path | None = None) -> ModernGuiState:
    settings = load_settings()
    save_dir = settings.default_save_location or str(default_dir or Path.home() / "Videos" / "Recordings")
    state = ModernGuiState(save_dir=_display_path(Path(save_dir).expanduser()))
    state.system_audio = bool(settings.record_system_audio)
    state.meeting_title = f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    return state


def _display_path(path: Path) -> str:
    try:
        return "~" + str(path).removeprefix(str(Path.home())) if str(path).startswith(str(Path.home())) else str(path)
    except Exception:
        return str(path)


def _fmt_elapsed(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _fmt_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "—"
    mb = size_bytes / 1_000_000
    return f"{mb:.1f} MB"


def _esc(value: object) -> str:
    return html_lib.escape(str(value), quote=True)


def render_modern_ui_html(state: ModernGuiState | None = None, *, bridge_url: str | None = None) -> str:
    state = state or ModernGuiState()
    rec_label = "Paused" if state.paused else ("Recording..." if state.recording else "Ready")
    body_class = "is-recording" if state.recording else "is-ready"
    bridge_script = f"window.MEETING_RECORDER_BRIDGE = {json.dumps(bridge_url)};" if bridge_url else "window.MEETING_RECORDER_BRIDGE = null;"
    initial_state = json.dumps(asdict(state))
    bars = "".join(f'<i class="bar {"dotbar" if h < 6 else ""}" style="height:{h}px"></i>' for h in WAVE_HEIGHTS)
    checked_system = "checked" if state.system_audio else ""
    checked_clicks = "checked" if state.show_clicks else ""
    hidden_save = "" if (state.saving or state.transcribing or state.saved or state.meeting_path) else " hidden"
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
  button,input,select{{font:inherit;color:inherit}} button{{border:0;padding:0;cursor:pointer}} input,select{{outline:0}}
  .wallpaper{{position:absolute;inset:0;background:radial-gradient(800px 480px at 18% 87%, rgba(202,119,65,.62), transparent 65%),radial-gradient(850px 520px at 80% 28%, rgba(70,93,134,.72), transparent 70%),radial-gradient(1200px 720px at 42% 52%, rgba(84,100,133,.72), transparent 75%),linear-gradient(135deg,#171b28 0%,#30394f 42%,#0c0f16 100%);filter:saturate(.95);}}
  .wallpaper:after{{content:"";position:absolute;inset:0;background:rgba(7,9,14,.36);backdrop-filter:blur(8px)}}
  .topbar{{position:absolute;top:0;left:0;right:0;height:68px;background:rgba(9,12,19,.64);backdrop-filter:blur(24px) saturate(1.25);box-shadow:0 1px 0 rgba(255,255,255,.06),0 18px 40px rgba(0,0,0,.22);display:flex;align-items:center;justify-content:center;gap:42px;font-size:24px;color:#e8edf7;letter-spacing:.01em;}}
  .topbar .icons{{display:flex;gap:42px;align-items:center}}.icon{{width:34px;height:34px;display:grid;place-items:center;color:#dce4f1}}.date{{font-size:24px;min-width:250px}}.tray{{width:68px;height:56px;border-radius:12px;border:1px solid rgba(77,143,255,.72);background:linear-gradient(180deg,rgba(45,57,82,.95),rgba(31,37,52,.85));box-shadow:0 0 0 1px rgba(31,119,255,.45),0 9px 28px rgba(0,0,0,.35),inset 0 1px rgba(255,255,255,.12);display:grid;place-items:center;position:relative}}.tray:before{{content:"";width:30px;height:30px;border-radius:50%;border:3px solid #ff8c9a;box-shadow:inset 0 0 0 8px #1c2230;background:#ff4053}}.tray:after{{content:"";position:absolute;bottom:-31px;border-left:22px solid transparent;border-right:22px solid transparent;border-bottom:22px solid rgba(16,19,28,.88);filter:drop-shadow(0 -1px 0 rgba(255,255,255,.12));}}
  .main-popover{{position:absolute;top:88px;left:315px;width:710px;height:800px;border-radius:24px;background:linear-gradient(145deg,rgba(22,25,34,.91),rgba(14,17,25,.84));backdrop-filter:blur(28px) saturate(1.35);border:1px solid var(--stroke);box-shadow:0 36px 90px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.08);padding:34px 36px;}}
  .head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}}.title{{font-size:29px;font-weight:760;letter-spacing:-.025em}}.head-actions{{display:flex;gap:18px}}.icon-btn{{font-size:27px;background:transparent;color:#c5cee0}}
  .status-row{{display:flex;align-items:center;gap:30px;margin-bottom:24px;font-size:24px}}.rec-dot{{width:25px;height:25px;border-radius:50%;border:3px solid var(--red);box-shadow:inset 0 0 0 5px rgba(255,78,93,.22)}}.is-ready .rec-dot{{border-color:var(--green);box-shadow:inset 0 0 0 5px rgba(98,210,130,.22)}}.rec-label{{color:var(--red);font-weight:650}}.is-ready .rec-label{{color:var(--green)}}.timer{{font-variant-numeric:tabular-nums;font-weight:570;letter-spacing:.03em}}.size{{margin-left:auto;color:#bac4d5;font-size:21px;display:flex;gap:12px;align-items:center}}
  .wave{{height:75px;display:flex;align-items:center;gap:5px;margin:6px 0 25px}}.bar{{width:4px;border-radius:6px;background:linear-gradient(#ff9ca8,#ff5362);opacity:.95;box-shadow:0 0 10px rgba(255,74,92,.2)}}.is-ready .bar{{background:linear-gradient(#6ea7ff,#287fff);opacity:.45}}.dotbar{{height:3px;opacity:.45}}
  .controls{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:22px;margin-bottom:18px}}.control{{height:120px;border-radius:18px;border:1px solid var(--stroke2);background:linear-gradient(180deg,rgba(43,48,63,.68),rgba(19,22,31,.72));display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;font-size:19px;box-shadow:inset 0 1px rgba(255,255,255,.06),0 8px 20px rgba(0,0,0,.16)}}.control.stop{{background:linear-gradient(180deg,#e2414c,#c32631);border-color:rgba(255,115,125,.38);box-shadow:0 16px 40px rgba(198,38,49,.32), inset 0 1px rgba(255,255,255,.18)}}.control.start{{background:linear-gradient(180deg,#2d8cff,#1e68d6)}}.control:disabled{{opacity:.38;cursor:not-allowed}}
  .settings{{height:388px;border-radius:15px;border:1px solid var(--stroke2);background:linear-gradient(180deg,rgba(31,35,47,.55),rgba(18,21,30,.44));padding:17px 20px}}.settings-title{{color:var(--muted);font-size:18px;margin-bottom:13px}}.row{{height:53px;display:grid;grid-template-columns:32px 1fr 318px;align-items:center;gap:14px;font-size:20px;color:#dfe5ef}}.row span{{font-size:25px;color:#d1d9e7}}.select,.path,input.glass{{height:45px;border-radius:10px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(180deg,rgba(45,50,63,.72),rgba(29,33,44,.72));display:flex;align-items:center;padding:0 14px;color:#ccd5e4;box-shadow:inset 0 1px rgba(255,255,255,.05);width:100%}}.switch{{justify-self:end;width:62px;height:34px;accent-color:#287fff}}.folder-row{{display:flex;gap:8px}}.folder-btn{{width:52px;height:45px;border-radius:10px;background:rgba(45,50,63,.72);border:1px solid rgba(255,255,255,.10);display:grid;place-items:center;color:#dce5f2}}
  .save-panel{{position:absolute;top:252px;left:1063px;width:504px;min-height:370px;border-radius:23px;background:linear-gradient(145deg,rgba(23,26,36,.91),rgba(15,18,26,.82));border:1px solid var(--stroke);box-shadow:0 34px 80px rgba(0,0,0,.4), inset 0 1px rgba(255,255,255,.08);backdrop-filter:blur(28px) saturate(1.35);padding:34px 36px}}.save-panel[hidden]{{display:none}}.save-head{{display:flex;align-items:center;gap:22px;font-size:23px;margin-bottom:24px}}.label{{font-size:21px;color:#cbd3e2;margin-bottom:10px}}.input{{height:51px;border-radius:8px;border:1px solid rgba(58,145,255,.95);box-shadow:0 0 0 1px rgba(28,116,255,.25), inset 0 1px rgba(255,255,255,.06);background:rgba(19,23,32,.74);display:flex;align-items:center;padding:0 16px;font-size:22px;color:#eef3fb;margin-bottom:25px}}.primary{{height:54px;border-radius:9px;background:linear-gradient(180deg,#2d8cff,#1e68d6);display:flex;align-items:center;justify-content:center;gap:16px;font-size:22px;font-weight:660;box-shadow:0 13px 28px rgba(32,112,226,.32);margin-bottom:27px;width:100%}}.divider{{height:1px;background:rgba(255,255,255,.12);margin-bottom:24px}}.progress{{display:grid;grid-template-columns:50px 1fr 34px;gap:0 0}}.rail{{grid-row:1/4;display:flex;flex-direction:column;align-items:center}}.node{{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#236fd6;font-size:20px}}.node.mid{{margin-top:50px;background:#192133;border:4px solid #2f74d6}}.node.done{{margin-top:55px;background:#62c779;color:#102316}}.line{{width:2px;height:49px;background:rgba(145,160,184,.45)}}.step{{height:83px}}.step-title{{font-size:19px;font-weight:650;margin-top:1px}}.step-sub{{font-size:17px;color:var(--muted);margin-top:7px}}.check{{color:#4fe07c;font-size:26px}}.spinner{{width:26px;height:26px;border:3px solid rgba(160,170,190,.25);border-top-color:#9da8ba;border-radius:50%}}.external{{color:#b9c2d2;font-size:26px}}.link{{color:#3993ff;margin-top:8px;font-size:18px;background:transparent;text-align:left}}.error{{color:#ff9ca8;font-size:16px;margin-top:8px;min-height:20px}}
</style>
</head><body class="{body_class}">
<div class="wallpaper"></div>
<div class="topbar"><div class="icons"><div class="icon">☼</div><div class="icon">⌁</div><div class="icon">♬</div><div class="icon">▭</div></div><button class="tray" data-action="toggle-panel" title="Meeting Recorder"></button><div class="date" id="current-date">{datetime.now().strftime('%a %b %-d  %I:%M %p')}</div></div>
<section class="main-popover">
  <div class="head"><div class="title">Meeting Recorder</div><div class="head-actions"><button class="icon-btn" data-action="settings">⚙</button><button class="icon-btn" data-action="menu">⋮</button></div></div>
  <div class="status-row"><div class="rec-dot"></div><div class="rec-label" id="rec-label">{rec_label}</div><div class="timer" id="timer">{_fmt_elapsed(state.elapsed_seconds)}</div><div class="size">⌁ <span id="size">{_fmt_size(state.size_bytes)}</span></div></div>
  <div class="wave" aria-label="waveform">{bars}</div>
  <div class="controls"><button class="control start" data-action="start" id="start-btn"><div class="glyph" style="font-size:38px">●</div><div>Start</div></button><button class="control" data-action="pause" id="pause-btn"><div class="glyph" style="font-size:38px">Ⅱ</div><div>Pause</div></button><button class="control stop" data-action="stop" id="stop-btn"><div class="glyph" style="font-size:37px">■</div><div>Stop</div></button></div>
  <div class="settings"><div class="settings-title">Settings</div>
    <div class="row"><span>♬</span><label for="microphone">Microphone</label><select class="select" id="microphone"><option>{_esc(state.microphone)}</option><option>Default microphone</option></select></div>
    <div class="row"><span>▭</span><label for="system-audio">System audio</label><input class="switch" id="system-audio" type="checkbox" {checked_system}></div>
    <div class="row"><span>□</span><label for="record-area">Record area</label><select class="select" id="record-area"><option>{_esc(state.record_area)}</option><option>Full screen</option><option>Audio only</option></select></div>
    <div class="row"><span>⌖</span><label for="show-clicks">Show mouse clicks</label><input class="switch" id="show-clicks" type="checkbox" {checked_clicks}></div>
    <div class="row"><span>◷</span><label for="countdown">Countdown</label><select class="select" id="countdown"><option>{_esc(state.countdown)}</option><option>None</option><option>3 seconds</option><option>5 seconds</option></select></div>
    <div class="row"><span>▱</span><label for="save-dir">Save to</label><div class="folder-row"><input class="glass" id="save-dir" value="{_esc(state.save_dir)}"><button class="folder-btn" data-action="choose-folder" title="Choose folder">▣</button></div></div>
  </div>
  <div class="error" id="error">{_esc(state.error)}</div>
</section>
<section class="save-panel" id="save-panel"{hidden_save}>
  <div class="save-head"><button class="icon-btn" data-action="back">‹</button><span>Save Recording</span></div>
  <div class="label">Session name</div><input id="session-title" class="input" value="{_esc(state.meeting_title)}"><button class="primary" data-action="save" id="save-btn">✦ Save &amp; Transcribe</button><div class="divider"></div>
  <div class="progress"><div class="rail"><div class="node">✓</div><div class="line"></div><div class="node mid"></div><div class="line"></div><div class="node done">✓</div></div>
    <div class="step"><div class="step-title" id="save-stage">Ready to save</div><div class="step-sub" id="save-sub">Recording will be saved to <span>{_esc(state.save_dir)}</span></div></div><div class="check">✓</div>
    <div class="step"><div class="step-title" id="transcribe-stage">Transcription waiting</div><div class="step-sub">Runs only after a real recording is saved</div></div><div class="spinner"></div>
    <div class="step"><div class="step-title">Transcript</div><button class="link" data-action="open-transcript" id="open-transcript">Open transcript</button></div><div class="external">↗</div>
  </div>
</section>
<script>
{bridge_script}
window.MEETING_RECORDER_STATE = {initial_state};
function formatElapsed(seconds) {{ seconds = Math.max(0, Number(seconds || 0)); const h=String(Math.floor(seconds/3600)).padStart(2,'0'); const m=String(Math.floor((seconds%3600)/60)).padStart(2,'0'); const s=String(seconds%60).padStart(2,'0'); return `${{h}}:${{m}}:${{s}}`; }}
function formatSize(bytes) {{ bytes = Number(bytes || 0); return bytes > 0 ? `${{(bytes/1000000).toFixed(1)}} MB` : '—'; }}
function collectForm() {{ return {{meeting_title:document.getElementById('session-title')?.value, save_dir:document.getElementById('save-dir')?.value, microphone:document.getElementById('microphone')?.value, system_audio:document.getElementById('system-audio')?.checked, record_area:document.getElementById('record-area')?.value, show_clicks:document.getElementById('show-clicks')?.checked, countdown:document.getElementById('countdown')?.value}}; }}
function renderState(state) {{
  window.MEETING_RECORDER_STATE = state;
  document.body.className = state.recording ? 'is-recording' : 'is-ready';
  document.getElementById('rec-label').textContent = state.paused ? 'Paused' : (state.recording ? 'Recording...' : 'Ready');
  document.getElementById('timer').textContent = formatElapsed(state.elapsed_seconds);
  document.getElementById('size').textContent = formatSize(state.size_bytes);
  document.getElementById('start-btn').disabled = !!state.recording;
  document.getElementById('pause-btn').disabled = !state.recording || !!state.paused;
  document.getElementById('stop-btn').disabled = !state.recording;
  document.getElementById('save-panel').hidden = !(state.saving || state.transcribing || state.saved || state.meeting_path);
  document.getElementById('error').textContent = state.error || '';
  document.getElementById('save-stage').textContent = state.saved ? 'Recording saved' : (state.saving ? 'Saving recording...' : 'Ready to save');
  document.getElementById('transcribe-stage').textContent = state.transcribing ? 'Transcribing audio...' : (state.transcript_path ? 'Transcript saved locally' : 'Transcription waiting');
  document.getElementById('open-transcript').disabled = !state.transcript_path;
}}
async function loadState() {{
  if (!window.MEETING_RECORDER_BRIDGE) {{ renderState(window.MEETING_RECORDER_STATE); return; }}
  const response = await fetch(window.MEETING_RECORDER_BRIDGE + '/state');
  const payload = await response.json();
  if (payload.ok) renderState(payload.state);
}}
async function bridge(action) {{
  if (action === 'toggle-panel' || action === 'menu' || action === 'back') {{ return; }}
  if (action === 'choose-folder') {{ const path = prompt('Save recordings to folder:', document.getElementById('save-dir').value); if (path) document.getElementById('save-dir').value = path; action = 'settings'; }}
  if (!window.MEETING_RECORDER_BRIDGE) return;
  const response = await fetch(window.MEETING_RECORDER_BRIDGE + '/action/' + action, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(collectForm())}}).catch(() => null);
  if (!response) return;
  const payload = await response.json();
  if (payload.state) renderState(payload.state); else await loadState();
}}
document.querySelectorAll('[data-action]').forEach(el => el.addEventListener('click', () => bridge(el.dataset.action)));
document.querySelectorAll('input,select').forEach(el => el.addEventListener('change', () => bridge('settings')));
loadState();
setInterval(loadState, 1000);
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
    cache_dir = Path(os.environ.get("MEETING_RECORDER_RENDER_DIR", Path.home() / "meeting-recorder-render-cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="meeting-recorder-ui-", dir=str(cache_dir)) as td:
        evidence_state = ModernGuiState(recording=True, elapsed_seconds=157, size_bytes=24_800_000, meeting_title="Team Sync – May 20, 2025", saving=True, transcribing=True)
        html = write_modern_ui_html(Path(td) / "meeting-recorder-modern.html", evidence_state)
        browser_output = Path(td) / "meeting-recorder-modern.png"
        last_error: Exception | None = None
        for browser in _browser_candidates():
            if _is_electron(browser):
                continue
            cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox", f"--window-size={APP_WIDTH},{APP_HEIGHT}", f"--screenshot={browser_output}", html.as_uri()]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if browser_output.exists() and browser_output.stat().st_size > 0:
                    shutil.copyfile(browser_output, output_path)
                    return output_path
            except Exception as exc:  # pragma: no cover - exercised in release smoke
                last_error = exc
        raise RuntimeError(f"No Chromium-compatible browser could render the modern GUI screenshot. Tried: {_browser_candidates()}. Last error: {last_error}")


class ModernBridgeService:
    """Local JSON bridge for the WebView frontend and recorder backend."""

    def __init__(self, default_dir: Path, backend: Any | None = None):
        self.default_dir = Path(default_dir)
        self.backend = backend
        self.state = default_state(default_dir)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._started_at: datetime | None = None
        self._elapsed_before_pause = 0

    @property
    def url(self) -> str:
        if not self._server:
            raise RuntimeError("bridge service is not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def _current_state_dict(self) -> dict[str, Any]:
        if self.state.recording and not self.state.paused and self._started_at:
            self.state.elapsed_seconds = self._elapsed_before_pause + int((datetime.now() - self._started_at).total_seconds())
        return asdict(self.state)

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
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/state":
                    self._json(200, {"ok": True, "state": service._current_state_dict(), "now": datetime.now().isoformat(timespec="seconds")})
                    return
                self._json(404, {"ok": False, "error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                action = urlparse(self.path).path.removeprefix("/action/")
                if action not in {"start", "pause", "resume", "stop", "save", "settings", "open-transcript"}:
                    self._json(404, {"ok": False, "error": "unknown action"})
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                form: dict[str, Any] = {}
                if length:
                    try:
                        form = json.loads(self.rfile.read(length).decode("utf-8"))
                    except json.JSONDecodeError:
                        form = {}
                result = service.dispatch(action, form)
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

    def _apply_form(self, form: dict[str, Any] | None) -> None:
        if not form:
            return
        for key in ["meeting_title", "save_dir", "microphone", "record_area", "countdown"]:
            if key in form and form[key] is not None:
                setattr(self.state, key, str(form[key]))
        for key in ["system_audio", "show_clicks"]:
            if key in form and form[key] is not None:
                setattr(self.state, key, bool(form[key]))

    def dispatch(self, action: str, form: dict[str, Any] | None = None) -> dict[str, Any]:
        self._apply_form(form)
        backend_result: dict[str, Any] = {}
        if self.backend and hasattr(self.backend, "configure"):
            try:
                self.backend.configure(self.state)
            except Exception as exc:
                self.state.error = str(exc)
                return {"ok": False, "action": action, "error": str(exc), "state": self._current_state_dict()}
        method_name = action.replace("-", "_")
        if self.backend and hasattr(self.backend, method_name):
            try:
                value = getattr(self.backend, method_name)()
            except Exception as exc:
                self.state.error = str(exc)
                return {"ok": False, "action": action, "error": str(exc), "state": self._current_state_dict()}
            backend_result = value if isinstance(value, dict) else {"result": value}
        if action == "start":
            self.state.recording = True
            self.state.paused = False
            self.state.saving = False
            self.state.transcribing = False
            self.state.saved = False
            self.state.error = ""
            self.state.size_bytes = 0
            self.state.elapsed_seconds = 0
            self._elapsed_before_pause = 0
            self._started_at = datetime.now()
        elif action == "pause":
            if self.state.recording and not self.state.paused:
                self.state.elapsed_seconds = self._current_state_dict()["elapsed_seconds"]
                self._elapsed_before_pause = self.state.elapsed_seconds
                self.state.paused = True
                self._started_at = None
        elif action == "resume":
            if self.state.recording:
                self.state.paused = False
                self._started_at = datetime.now()
        elif action in {"stop", "save"}:
            self.state.recording = False
            self.state.paused = False
            self.state.saving = False
            self.state.transcribing = False
            self.state.saved = True
            self._started_at = None
        for key in ["recording", "paused", "meeting_path", "media_path", "transcript_path", "size_bytes", "error"]:
            if key in backend_result:
                setattr(self.state, key, backend_result[key])
        if self.state.recording is False:
            self.state.paused = False
        return {"ok": not bool(self.state.error), "action": action, "result": backend_result, "state": self._current_state_dict()}


class RecorderBridgeBackend:
    """Adapter from modern UI actions to the existing Python recorder backend."""

    def __init__(self, default_dir: Path):
        self.default_dir = Path(default_dir)
        self.recorder: Any | None = None
        self.raw_file: Path | None = None
        self.ui_state = ModernGuiState(save_dir=_display_path(self.default_dir))

    def configure(self, state: ModernGuiState) -> None:
        self.ui_state = state

    def _output_dir(self) -> Path:
        value = self.ui_state.save_dir or str(self.default_dir)
        return Path(value).expanduser()

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
        include_video = bool(settings.record_video and self.ui_state.record_area != "Audio only")
        self.recorder = start_recording(
            self.raw_file,
            fps=settings.fps,
            size=settings.size or None,
            include_system_audio=bool(self.ui_state.system_audio),
            include_mic=bool(settings.record_microphone),
            include_video=include_video,
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
            self._output_dir(),
            self.ui_state.meeting_title or f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}",
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

    def open_transcript(self) -> dict[str, Any]:
        return {"transcript_path": self.ui_state.transcript_path}


def launch_modern_gui(default_dir: Path) -> int:
    bridge = ModernBridgeService(default_dir, backend=RecorderBridgeBackend(default_dir)).start()
    cache_dir = Path(os.environ.get("MEETING_RECORDER_RENDER_DIR", Path.home() / "meeting-recorder-render-cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="meeting-recorder-ui-", dir=str(cache_dir)) as td:
        html = write_modern_ui_html(Path(td) / "meeting-recorder-modern.html", default_state(default_dir), bridge_url=bridge.url)
        browser = _browser_candidates()[0] if _browser_candidates() else None
        if not browser:
            bridge.stop()
            raise RuntimeError("No Electron/Chromium-compatible runtime found. Install Electron or Chromium to launch the modern GUI.")
        if _is_electron(browser):
            cmd = [browser, "--no-sandbox", html.as_uri()]
        else:
            cmd = [browser, "--no-sandbox", "--app=" + html.as_uri(), f"--window-size={APP_WIDTH},{APP_HEIGHT}"]
        try:
            return subprocess.call(cmd)
        finally:
            bridge.stop()
