"""Capture-loop policy: what gets kept, and what touches the disk/executor.

The loop hashes every frame (change detection needs it) but must only save
screenshots for frames that survive the dedup/heartbeat filter — saving first
orphaned a uniquely-named file on every skipped tick.
"""
import asyncio
from unittest.mock import patch

from PIL import Image

from brn_daemon.dedup import compute_phash
from brn_daemon.main import _save_screenshot_off_loop, _select_pending

# Two genuinely different frames → different phashes (solid black vs half white)
_IMG_A = Image.new("RGB", (64, 64), color=0)
_IMG_B = Image.new("RGB", (64, 64), color=0)
_IMG_B.paste((255, 255, 255), (0, 0, 32, 64))
PHASH_A = compute_phash(_IMG_A)
PHASH_B = compute_phash(_IMG_B)


def _candidate(monitor_idx: int = 1, app: str = "Code"):
    return (monitor_idx, _IMG_A, {"left": 0, "top": 0}, app, "window")


# ── _select_pending: the keep/skip policy ───────────────────────────────────


def test_unchanged_frame_on_non_heartbeat_tick_is_skipped():
    prev = {1: PHASH_A}
    kept = _select_pending([_candidate()], [PHASH_A], prev, is_heartbeat=False)
    assert kept == []


def test_changed_frame_is_kept_with_change_trigger():
    prev = {1: PHASH_A}
    kept = _select_pending([_candidate()], [PHASH_B], prev, is_heartbeat=False)
    assert len(kept) == 1
    assert kept[0][5] == "change"  # trigger


def test_heartbeat_keeps_even_unchanged_frames():
    prev = {1: PHASH_A}
    kept = _select_pending([_candidate()], [PHASH_A], prev, is_heartbeat=True)
    assert len(kept) == 1
    assert kept[0][5] == "heartbeat"


def test_first_frame_ever_is_kept():
    kept = _select_pending([_candidate()], [PHASH_A], {}, is_heartbeat=False)
    assert len(kept) == 1


def test_prev_phash_updated_only_for_kept_frames():
    prev = {1: PHASH_A, 2: PHASH_A}
    kept = _select_pending(
        [_candidate(1), _candidate(2)],
        [PHASH_A, PHASH_B],  # m1 unchanged (skip), m2 changed (keep)
        prev,
        is_heartbeat=False,
    )
    assert [k[0] for k in kept] == [2]
    assert prev[1] == PHASH_A  # untouched
    assert prev[2] == PHASH_B  # advanced to the kept frame


# ── executor offloading ─────────────────────────────────────────────────────


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
            await _save_screenshot_off_loop(loop, _IMG_A, key=None, monitor_index=1)

    assert "save_screenshot" in executor_funcs
