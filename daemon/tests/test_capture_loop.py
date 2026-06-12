"""Capture-loop plumbing: what touches the disk/executor, and OCR reuse.

The keep/skip policy itself is covered in test_capture_policy.py.
"""
import asyncio
from unittest.mock import patch

from PIL import Image

from brn_daemon.capture_policy import Frame, KeptFrame
from brn_daemon.main import _MonitorMemo, _ocr_kept_frames, _save_screenshot_off_loop

_IMG = Image.new("RGB", (64, 64), color=0)


def _kept(monitor_idx: int = 1, unchanged: bool = False) -> KeptFrame:
    frame = Frame(
        monitor_index=monitor_idx,
        image=_IMG,
        monitor_rect={"left": 0, "top": 0},
        app_name="Code",
        window_title="window",
    )
    return KeptFrame(frame=frame, trigger="heartbeat", phash="0" * 16, unchanged=unchanged)


# ── _ocr_kept_frames: reuse for unchanged heartbeats ────────────────────────


async def test_unchanged_heartbeat_reuses_memoised_ocr():
    memos = {1: _MonitorMemo(capture_id=7, ocr_text="hello world")}
    with patch("brn_daemon.main.extract_text") as mock_ocr:
        results = await _ocr_kept_frames(
            asyncio.get_running_loop(), [_kept(unchanged=True)], memos
        )
    assert results == [("hello world", True)]
    mock_ocr.assert_not_called()


async def test_changed_frame_gets_fresh_ocr():
    memos = {1: _MonitorMemo(capture_id=7, ocr_text="stale")}
    with patch("brn_daemon.main.extract_text", return_value="fresh text") as mock_ocr:
        results = await _ocr_kept_frames(
            asyncio.get_running_loop(), [_kept(unchanged=False)], memos
        )
    assert results == [("fresh text", False)]
    mock_ocr.assert_called_once()


async def test_unchanged_frame_without_memo_falls_back_to_fresh_ocr():
    """First heartbeat after daemon start has nothing to reuse."""
    with patch("brn_daemon.main.extract_text", return_value="fresh text"):
        results = await _ocr_kept_frames(asyncio.get_running_loop(), [_kept(unchanged=True)], {})
    assert results == [("fresh text", False)]


async def test_mixed_batch_preserves_frame_order():
    memos = {1: _MonitorMemo(capture_id=7, ocr_text="cached")}
    kept = [_kept(1, unchanged=True), _kept(2, unchanged=False)]
    with patch("brn_daemon.main.extract_text", return_value="fresh"):
        results = await _ocr_kept_frames(asyncio.get_running_loop(), kept, memos)
    assert results == [("cached", True), ("fresh", False)]


async def test_save_screenshot_offloaded_to_executor(tmp_home):
    """save_screenshot must run via run_in_executor, not on the loop."""
    executor_funcs = []
    loop = asyncio.get_running_loop()
    original_run = loop.run_in_executor

    def tracking_run(executor, fn, *args):
        name = getattr(fn, "__name__", None) or "unknown"
        executor_funcs.append(name)
        return original_run(executor, fn, *args)

    with patch.object(loop, "run_in_executor", side_effect=tracking_run):
        with patch("brn_daemon.main.save_screenshot", return_value="/tmp/fake.jpg"):
            await _save_screenshot_off_loop(loop, _IMG, key=None, monitor_index=1)

    assert "save_screenshot" in executor_funcs
