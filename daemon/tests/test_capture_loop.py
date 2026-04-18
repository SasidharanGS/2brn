"""Tests that CPU-intensive capture operations are offloaded to an executor."""
import asyncio
import functools
from unittest.mock import patch
import pytest
from PIL import Image


async def test_compute_phash_offloaded_to_executor(tmp_home, monkeypatch):
    """compute_phash must be called via run_in_executor, not directly on the loop."""
    executor_funcs = []
    loop = asyncio.get_running_loop()
    original_run = loop.run_in_executor

    async def tracking_run(executor, fn, *args):
        name = getattr(fn, "__name__", None) or getattr(getattr(fn, "func", None), "__name__", "unknown")
        executor_funcs.append(name)
        return await original_run(executor, fn, *args)

    fake_img = Image.new("RGB", (4, 4))

    with patch.object(loop, "run_in_executor", side_effect=tracking_run):
        with patch("brn_daemon.main.save_screenshot", return_value="/tmp/fake.jpg"):
            from brn_daemon.main import _phase1_process_monitor
            await _phase1_process_monitor(loop, fake_img, key=None)

    assert "compute_phash" in executor_funcs, (
        f"compute_phash not offloaded to executor. Got: {executor_funcs}"
    )
    assert "save_screenshot" in executor_funcs, (
        f"save_screenshot not offloaded to executor. Got: {executor_funcs}"
    )
