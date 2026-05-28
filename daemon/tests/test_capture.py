import sys
import pytest
from PIL import Image
import numpy as np

def _make_mock_screenshot(color=(100, 100, 100)):
    arr = np.full((200, 300, 3), color, dtype=np.uint8)
    return Image.fromarray(arr)

def test_get_active_app_returns_string():
    from brn_daemon.capture import get_active_app
    app_name, window_title = get_active_app()
    assert isinstance(app_name, str)
    assert isinstance(window_title, str)

def test_save_screenshot_creates_file(tmp_home):
    from brn_daemon.capture import save_screenshot
    from brn_daemon.db import get_brn_home
    img = _make_mock_screenshot()
    path = save_screenshot(img)
    assert path.exists()
    assert path.suffix == ".jpg"
    assert str(get_brn_home()) in str(path)

def test_save_screenshot_nested_by_date(tmp_home):
    from brn_daemon.capture import save_screenshot
    img = _make_mock_screenshot()
    path = save_screenshot(img)
    # path format: ~/.2brn/screenshots/YYYY/MM/DD/<timestamp>.jpg
    # check that there are at least 4 path components after screenshots/
    parts = path.parts
    screenshots_idx = next(i for i, p in enumerate(parts) if p == "screenshots")
    date_parts = parts[screenshots_idx+1:]
    assert len(date_parts) >= 4  # YYYY / MM / DD / filename.jpg


# ── Per-monitor app detection tests ──────────────────────────────────────────

def test_get_windows_snapshot_returns_list():
    from brn_daemon.capture import get_windows_snapshot
    result = get_windows_snapshot()
    assert isinstance(result, list)


def test_get_app_for_monitor_no_windows_falls_back():
    """Empty windows list → falls back to get_active_app(), returns strings."""
    from brn_daemon.capture import get_app_for_monitor
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    app_name, window_title = get_app_for_monitor(monitor, [])
    assert isinstance(app_name, str)
    assert isinstance(window_title, str)


def _make_window(owner: str, title: str, x: int, y: int, w: int, h: int, layer: int = 0) -> dict:
    return {
        "kCGWindowOwnerName": owner,
        "kCGWindowName": title,
        "kCGWindowLayer": layer,
        "kCGWindowBounds": {"X": float(x), "Y": float(y), "Width": float(w), "Height": float(h)},
    }


@pytest.mark.skipif(sys.platform != "darwin", reason="kCGWindow keys are macOS-only")
def test_get_app_for_monitor_picks_largest_overlap():
    """Window with larger overlap area should win."""
    from brn_daemon.capture import get_app_for_monitor
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    small_win = _make_window("Small", "Small Window", 0, 0, 100, 100)       # 100×100 = 10 000 px²
    large_win = _make_window("Large", "Large Window", 0, 0, 1920, 1080)     # fills monitor = 2 073 600 px²
    app_name, window_title = get_app_for_monitor(monitor, [small_win, large_win])
    assert app_name == "Large"
    assert window_title == "Large Window"


def test_get_app_for_monitor_skips_negative_layers():
    """Windows with layer < 0 (desktop/Finder) must be skipped."""
    from brn_daemon.capture import get_app_for_monitor
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    desktop_win = _make_window("Finder", "Desktop", 0, 0, 1920, 1080, layer=-2147483630)
    # Only the desktop window exists — should fall back, not return "Finder"
    app_name, _ = get_app_for_monitor(monitor, [desktop_win])
    assert app_name != "Finder"


@pytest.mark.skipif(sys.platform != "darwin", reason="kCGWindow keys are macOS-only")
def test_get_app_for_monitor_skips_high_layers():
    """Windows with layer > 25 (menu bar, overlays) must be skipped."""
    from brn_daemon.capture import get_app_for_monitor
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    overlay_win = _make_window("SystemUIServer", "Menu Bar", 0, 0, 1920, 30, layer=25)
    high_win = _make_window("SystemUIServer", "Overlay", 0, 0, 1920, 30, layer=26)
    # layer=25 is allowed (boundary), layer=26 is skipped
    app_name_25, _ = get_app_for_monitor(monitor, [overlay_win])
    assert app_name_25 == "SystemUIServer"
    app_name_26, _ = get_app_for_monitor(monitor, [high_win])
    assert app_name_26 != "SystemUIServer"


def test_save_screenshot_encrypted_writes_enc_file(tmp_home):
    """When a key is passed, the file is written with a .jpg.enc suffix and the bytes round-trip."""
    from brn_daemon.capture import save_screenshot
    from brn_daemon.encryption import ENCRYPTED_EXT, decrypt_bytes, derive_key, SALT_LENGTH
    key = derive_key("test-password-1234", b"\x11" * SALT_LENGTH)
    img = _make_mock_screenshot(color=(50, 100, 150))
    path = save_screenshot(img, key=key)
    assert path.exists()
    assert str(path).endswith(ENCRYPTED_EXT)

    # Decrypt and verify it's a valid JPEG (starts with JPEG SOI marker 0xFFD8)
    pt = decrypt_bytes(path.read_bytes(), key)
    assert pt[:2] == b"\xff\xd8"


@pytest.mark.skipif(sys.platform != "darwin", reason="mss requires a display; Linux CI is headless")
def test_capture_all_monitors_with_rects_returns_tuples():
    """Each element should be (int, PIL.Image, dict with left/top/width/height)."""
    from brn_daemon.capture import capture_all_monitors_with_rects
    results = capture_all_monitors_with_rects()
    assert isinstance(results, list)
    assert len(results) >= 1
    for monitor_idx, img, rect in results:
        assert isinstance(monitor_idx, int)
        assert monitor_idx >= 1
        assert isinstance(img, Image.Image)
        assert isinstance(rect, dict)
        for key in ("left", "top", "width", "height"):
            assert key in rect

