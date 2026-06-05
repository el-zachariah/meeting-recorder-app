from __future__ import annotations

from typing import Any, Callable


class TrayBackendUnavailable(RuntimeError):
    """Raised when the native system tray dependency stack is unavailable."""


TRAY_DEPENDENCY_MESSAGE = (
    "Meeting Recorder needs native system tray support for the GUI. "
    "Install it with: sudo apt install python3-pystray python3-pil. "
    "If your desktop hides tray icons, enable an AppIndicator/system-tray extension."
)


def require_tray_backend() -> tuple[Any, Any, Any]:
    """Return imported tray/image modules or raise an actionable error.

    The GUI requirement is a real system tray icon, not a floating corner window.
    Therefore missing tray dependencies are a hard startup error instead of a
    silent fallback to a top-right Tk window.
    """

    try:
        import pystray  # type: ignore[import-not-found]
        from PIL import Image, ImageDraw  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - exact import failure depends on distro
        raise TrayBackendUnavailable(TRAY_DEPENDENCY_MESSAGE) from exc
    if pystray is None or Image is None or ImageDraw is None:
        raise TrayBackendUnavailable(TRAY_DEPENDENCY_MESSAGE)
    return pystray, Image, ImageDraw


def build_tray_image() -> Any:
    _pystray, Image, ImageDraw = require_tray_backend()
    image = Image.new("RGBA", (64, 64), (8, 9, 10, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=(113, 112, 255, 255))
    draw.ellipse((23, 23, 41, 41), fill=(247, 248, 248, 255))
    return image


def _schedule(root: Any, callback: Callable[[], None]) -> None:
    root.after(0, callback)


def pump_glib_events(root: Any, *, interval_ms: int = 50) -> None:
    """Let GTK/AppIndicator process pending events while Tk owns mainloop.

    pystray's Linux AppIndicator backend schedules visibility/menu updates on
    GLib. When Meeting Recorder runs Tk's mainloop, those GLib idle callbacks do
    not run unless we explicitly drain the default context. Without this, Pop!_OS
    can have a functioning tray for Discord/Zoom while Meeting Recorder remains
    invisible.
    """

    try:
        from gi.repository import GLib  # type: ignore[import-not-found]
    except Exception:
        return

    def _pump() -> None:
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)
        try:
            root.after(interval_ms, _pump)
        except Exception:
            return

    root.after(interval_ms, _pump)


def start_tray_icon(app: Any, icon: Any) -> None:
    icon.run_detached()
    icon.visible = True
    pump_glib_events(app.root)


def create_tray_icon(app: Any) -> Any:
    """Create the native system tray icon and menu for the Tk app.

    `app` must expose root.after plus show_tray_dropdown(), toggle_recording(),
    and shutdown(). Keeping this adapter small makes it testable without opening
    a real display or tray.
    """

    pystray, _Image, _ImageDraw = require_tray_backend()
    image = build_tray_image()

    def open_dropdown(_icon: Any, _item: Any = None) -> None:
        _schedule(app.root, app.show_tray_dropdown)

    def toggle_recording(_icon: Any, _item: Any = None) -> None:
        _schedule(app.root, app.toggle_recording)

    def quit_app(_icon: Any, _item: Any = None) -> None:
        _schedule(app.root, app.shutdown)

    return pystray.Icon(
        "meeting-recorder",
        image,
        "Meeting Recorder",
        pystray.Menu(
            pystray.MenuItem("Open Meeting Recorder", open_dropdown, default=True),
            pystray.MenuItem("Start / Stop Recording", toggle_recording),
            pystray.MenuItem("Quit", quit_app),
        ),
    )
