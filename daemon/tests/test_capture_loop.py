"""Capture-loop plumbing: what touches the disk/executor.

The keep/skip policy itself is covered in test_capture_policy.py.
"""
import asyncio
from unittest.mock import patch

from PIL import Image

from brn_daemon.main import _save_screenshot_off_loop

_IMG = Image.new("RGB", (64, 64), color=0)


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
