"""Capture-loop plumbing: what touches the disk/executor, OCR reuse, and the
per-capture classification routing.

The keep/skip policy itself is covered in test_capture_policy.py.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from brn_daemon.capture_policy import Frame, KeptFrame
from brn_daemon.main import (
    _MonitorMemo,
    _ocr_kept_frames,
    _record_capture,
    _save_screenshot_off_loop,
    _SparseMemo,
)

_IMG = Image.new("RGB", (64, 64), color=0)

READABLE = "plenty of readable text extracted from this screen"


def _kept(
    monitor_idx: int = 1,
    unchanged: bool = False,
    app_name: str = "Code",
    window_title: str = "window",
) -> KeptFrame:
    frame = Frame(
        monitor_index=monitor_idx,
        image=_IMG,
        monitor_rect={"left": 0, "top": 0},
        app_name=app_name,
        window_title=window_title,
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


# ── _record_capture: classification routing ─────────────────────────────────


def _queue() -> MagicMock:
    queue = MagicMock()
    queue.enqueue = AsyncMock()
    return queue


async def _seed_classified_capture(db, summary: str = "Watching a film") -> int:
    """A capture that already has an activity — a valid clone source."""
    cur = await db.execute(
        "INSERT INTO captures (captured_at, app_name) VALUES ('2026-06-12T09:00:00', 'VLC')"
    )
    await db.commit()
    capture_id = cur.lastrowid
    await db.execute(
        "INSERT INTO activities (capture_id, started_at, summary, task_category) "
        "VALUES (?, '2026-06-12T09:00:00', ?, 'play')",
        (capture_id, summary),
    )
    await db.commit()
    return capture_id


async def _activity_count(db, *, exclude_capture: int | None = None) -> int:
    sql = "SELECT COUNT(*) FROM activities"
    if exclude_capture is not None:
        sql += f" WHERE capture_id != {exclude_capture}"
    cur = await db.execute(sql)
    return (await cur.fetchone())[0]


async def test_readable_text_goes_to_normal_inference(tmp_home, db):
    queue = _queue()
    ocr_memos: dict[int, _MonitorMemo] = {}

    await _record_capture(db, queue, _kept(), "/tmp/x.jpg", READABLE, False, ocr_memos, {})

    queue.enqueue.assert_awaited_once()
    assert queue.enqueue.await_args.args[3] == READABLE
    assert ocr_memos[1].ocr_text == READABLE  # becomes the monitor's fresh root


async def test_sparse_with_metadata_queues_metadata_only_inference(tmp_home, db):
    queue = _queue()
    sparse_memos: dict[int, _SparseMemo] = {}

    await _record_capture(
        db, queue, _kept(app_name="VLC", window_title="movie.mp4"),
        "/tmp/x.jpg", "x7@", False, {}, sparse_memos,
    )

    queue.enqueue.assert_awaited_once()
    memo = sparse_memos[1]
    assert (memo.app_name, memo.window_title) == ("VLC", "movie.mp4")


async def test_sparse_with_same_metadata_clones_instead_of_inferring(tmp_home, db):
    source_id = await _seed_classified_capture(db)
    queue = _queue()
    sparse_memos = {1: _SparseMemo(app_name="VLC", window_title="movie.mp4", capture_id=source_id)}

    await _record_capture(
        db, queue, _kept(app_name="VLC", window_title="movie.mp4"),
        "/tmp/x.jpg", "x7@", False, {}, sparse_memos,
    )

    queue.enqueue.assert_not_awaited()
    assert await _activity_count(db, exclude_capture=source_id) == 1  # the clone
    assert sparse_memos[1].capture_id == source_id  # root unchanged


async def test_sparse_with_new_metadata_reinfers(tmp_home, db):
    source_id = await _seed_classified_capture(db)
    queue = _queue()
    sparse_memos = {1: _SparseMemo(app_name="VLC", window_title="old.mp4", capture_id=source_id)}

    await _record_capture(
        db, queue, _kept(app_name="VLC", window_title="new.mp4"),
        "/tmp/x.jpg", "x7@", False, {}, sparse_memos,
    )

    queue.enqueue.assert_awaited_once()
    assert sparse_memos[1].window_title == "new.mp4"


async def test_sparse_memo_without_landed_activity_falls_back_to_inference(tmp_home, db):
    """If the memoised classification never landed, re-infer rather than leave a gap."""
    cur = await db.execute(
        "INSERT INTO captures (captured_at, app_name) VALUES ('2026-06-12T09:00:00', 'VLC')"
    )
    await db.commit()
    pending_id = cur.lastrowid  # capture with no activity row
    queue = _queue()
    sparse_memos = {1: _SparseMemo(app_name="VLC", window_title="movie.mp4", capture_id=pending_id)}

    await _record_capture(
        db, queue, _kept(app_name="VLC", window_title="movie.mp4"),
        "/tmp/x.jpg", "x7@", False, {}, sparse_memos,
    )

    queue.enqueue.assert_awaited_once()
    assert sparse_memos[1].capture_id != pending_id  # new root


async def test_sparse_without_metadata_stays_unclassified(tmp_home, db):
    queue = _queue()

    await _record_capture(
        db, queue, _kept(app_name="", window_title=""),
        "/tmp/x.jpg", "x7@", False, {}, {},
    )

    queue.enqueue.assert_not_awaited()
    assert await _activity_count(db) == 0
    cur = await db.execute("SELECT COUNT(*) FROM captures")
    assert (await cur.fetchone())[0] == 1  # still recorded


async def test_unchanged_heartbeat_clones_from_ocr_memo(tmp_home, db):
    source_id = await _seed_classified_capture(db)
    queue = _queue()
    ocr_memos = {1: _MonitorMemo(capture_id=source_id, ocr_text=READABLE)}

    await _record_capture(db, queue, _kept(unchanged=True), "/tmp/x.jpg", READABLE, True, ocr_memos, {})

    queue.enqueue.assert_not_awaited()
    assert await _activity_count(db, exclude_capture=source_id) == 1
    assert ocr_memos[1].capture_id == source_id  # reuse must not shift the root


async def test_unchanged_heartbeat_without_landed_activity_falls_back(tmp_home, db):
    cur = await db.execute(
        "INSERT INTO captures (captured_at, app_name) VALUES ('2026-06-12T09:00:00', 'Code')"
    )
    await db.commit()
    pending_id = cur.lastrowid
    queue = _queue()
    ocr_memos = {1: _MonitorMemo(capture_id=pending_id, ocr_text=READABLE)}

    await _record_capture(db, queue, _kept(unchanged=True), "/tmp/x.jpg", READABLE, True, ocr_memos, {})

    queue.enqueue.assert_awaited_once()
    assert ocr_memos[1].capture_id == pending_id  # root preserved for later clones
