import io
import logging
import platform
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import mss

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)

# Persistent mss instance — avoids CoreGraphics/D3D re-initialisation overhead on every tick.
# mss is not thread-safe; all calls must remain on the same thread (the asyncio event loop
# uses run_in_executor for CPU work, but capture itself stays on the main thread via the loop).
_mss_instance: mss.base.MssBase | None = None


def _get_mss() -> mss.base.MssBase:
    """Return the shared mss instance, creating it on first call."""
    global _mss_instance
    if _mss_instance is None:
        _mss_instance = mss.mss()
    return _mss_instance


def get_active_app() -> tuple[str, str]:
    """Return (app_name, window_title) for the currently focused window."""
    system = platform.system()
    try:
        if system == "Darwin":
            try:
                from AppKit import NSWorkspace  # type: ignore
                ws = NSWorkspace.sharedWorkspace()
                app = ws.frontmostApplication()
                app_name = app.localizedName() or ""
            except Exception:
                app_name = ""
            try:
                import Quartz  # type: ignore
                wins = Quartz.CGWindowListCopyWindowInfo(
                    Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                    Quartz.kCGNullWindowID,
                )
                for w in wins:
                    if w.get("kCGWindowOwnerName") == app_name and w.get("kCGWindowName"):
                        return app_name, w["kCGWindowName"]
            except Exception:
                pass
            return app_name, ""
        elif system == "Windows":
            try:
                import pygetwindow as gw  # type: ignore
                win = gw.getActiveWindow()
                if win:
                    title = win.title
                    parts = title.rsplit(" - ", 1)
                    return (parts[-1] if len(parts) > 1 else title), title
            except Exception:
                pass
            return "", ""
        else:
            # Linux: use xdotool
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            title = result.stdout.strip()
            return title, title
    except Exception as exc:
        logger.debug("Could not get active app: %s", exc)
        return "", ""


def _rect_overlap(w_bounds: dict, monitor: dict) -> float:
    """Return the intersection area (px²) between a Quartz window bounds dict and an mss monitor dict."""
    wx1, wy1 = w_bounds["X"], w_bounds["Y"]
    wx2, wy2 = wx1 + w_bounds["Width"], wy1 + w_bounds["Height"]
    mx1, my1 = monitor["left"], monitor["top"]
    mx2, my2 = mx1 + monitor["width"], my1 + monitor["height"]
    return max(0.0, min(wx2, mx2) - max(wx1, mx1)) * max(0.0, min(wy2, my2) - max(wy1, my1))


def get_windows_snapshot() -> list:
    """Fetch all on-screen Quartz windows once per cycle. Returns [] on non-macOS or on error.
    Call once outside the monitor loop and pass the result to get_app_for_monitor().
    """
    if platform.system() != "Darwin":
        return []
    try:
        import Quartz  # type: ignore
        return list(Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        ))
    except Exception:
        return []


def get_app_for_monitor(monitor_rect: dict, windows: list) -> tuple[str, str]:
    """Return (app_name, window_title) of the dominant window on the given monitor.

    Iterates the pre-fetched window snapshot and picks the window with the largest
    overlap area with `monitor_rect` (an mss monitor dict with keys left/top/width/height).
    Skips desktop layers (< 0) and overlay/menu-bar layers (> 25).
    kCGWindowName may be None for Electron apps — returns "" for title in that case.
    Falls back to get_active_app() if windows is empty or no overlap is found.
    """
    if not windows or platform.system() != "Darwin":
        return get_active_app()

    best_app, best_title, best_area = "", "", 0.0
    for w in windows:
        layer = w.get("kCGWindowLayer", 0)
        if layer < 0 or layer > 25:
            continue
        bounds = w.get("kCGWindowBounds")
        if not bounds:
            continue
        area = _rect_overlap(bounds, monitor_rect)
        if area > best_area:
            best_area = area
            best_app = w.get("kCGWindowOwnerName") or ""
            best_title = w.get("kCGWindowName") or ""

    if best_app:
        return best_app, best_title
    return get_active_app()


def capture_all_monitors_with_rects() -> list[tuple[int, "Image.Image", dict]]:
    """Like capture_all_monitors() but also returns the raw mss monitor dict per monitor.
    Each element: (monitor_index, PIL.Image, mss_monitor_dict).
    The mss_monitor_dict contains left/top/width/height for overlap detection.
    """
    sct = _get_mss()
    results = []
    for idx, monitor in enumerate(sct.monitors[1:], start=1):
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        results.append((idx, img, dict(monitor)))
    return results


def capture_screenshot() -> Image.Image:
    """Capture the primary monitor and return a PIL Image."""
    sct = _get_mss()
    monitor = sct.monitors[1]  # primary monitor
    raw = sct.grab(monitor)
    return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def capture_all_monitors() -> list[tuple[int, Image.Image]]:
    """Capture every connected monitor. Returns list of (monitor_index, image).
    monitor_index matches mss.monitors — starts at 1 (monitors[0] is the combined virtual screen).
    """
    sct = _get_mss()
    results = []
    for idx, monitor in enumerate(sct.monitors[1:], start=1):
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        results.append((idx, img))
    return results


def save_screenshot(image: Image.Image, *, key: bytes | None = None) -> Path:
    """Save screenshot as JPEG under ``~/.2brn/screenshots/YYYY/MM/DD/<ts>.jpg``.

    When ``key`` is provided, the JPEG bytes are encrypted with AES-256-GCM and the file is
    written with a ``.jpg.enc`` suffix instead. The encryption format is defined in
    ``brn_daemon.encryption``.
    """
    now = datetime.now(timezone.utc)
    dir_path = (
        get_brn_home()
        / "screenshots"
        / now.strftime("%Y")
        / now.strftime("%m")
        / now.strftime("%d")
    )
    dir_path.mkdir(parents=True, exist_ok=True)

    if key is None:
        file_path = dir_path / f"{now.strftime('%H%M%S_%f')}.jpg"
        image.save(file_path, "JPEG", quality=80)
        return file_path

    # Encrypted path: render JPEG into memory, encrypt, write blob.
    from brn_daemon.encryption import encrypt_bytes, ENCRYPTED_EXT
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=80)
    blob = encrypt_bytes(buf.getvalue(), key)
    file_path = dir_path / f"{now.strftime('%H%M%S_%f')}{ENCRYPTED_EXT}"
    file_path.write_bytes(blob)
    return file_path
