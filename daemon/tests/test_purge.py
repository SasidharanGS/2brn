from datetime import UTC, datetime, timedelta

import aiosqlite

from brn_daemon.db import get_brn_home, get_db_path, init_db
from brn_daemon.purge import purge_old_captures


async def test_purge_removes_old_screenshots(tmp_home):
    await init_db()
    screenshots_dir = get_brn_home() / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    old_file = screenshots_dir / "old.jpg"
    old_file.write_bytes(b"fake")
    new_file = screenshots_dir / "new.jpg"
    new_file.write_bytes(b"fake")

    old_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()
    new_date = datetime.now(UTC).isoformat()

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES (?, 'heartbeat', ?)",
            (old_date, str(old_file))
        )
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES (?, 'heartbeat', ?)",
            (new_date, str(new_file))
        )
        await conn.commit()

    await purge_old_captures(months=6)

    assert not old_file.exists()
    assert new_file.exists()

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM captures")
        count = (await cur.fetchone())[0]
    assert count == 1


async def test_purge_handles_missing_file_gracefully(tmp_home):
    await init_db()
    old_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES (?, 'heartbeat', ?)",
            (old_date, "/nonexistent/path.jpg")
        )
        await conn.commit()
    # Should not raise even though file doesn't exist
    await purge_old_captures(months=6)


async def test_purge_handles_more_than_999_captures(tmp_home, db):
    """Purge must not fail when capture count exceeds SQLite's 999-variable limit."""
    from datetime import datetime, timedelta

    import aiosqlite

    from brn_daemon.db import get_db_path
    from brn_daemon.purge import purge_old_captures

    cutoff = datetime.now(UTC) - timedelta(days=400)

    async with aiosqlite.connect(get_db_path()) as conn:
        for i in range(1001):
            ts = (cutoff - timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.%f")
            await conn.execute(
                "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text) "
                "VALUES (?, 'App', 'Win', NULL, '')",
                (ts,),
            )
        await conn.commit()

    purged = await purge_old_captures(months=12, chroma_store=None)
    assert purged == 1001


async def test_purge_returns_row_count_not_file_count(tmp_home, db):
    """purge_old_captures must return number of DB rows deleted, not files."""
    from datetime import datetime, timedelta

    import aiosqlite

    from brn_daemon.db import get_db_path
    from brn_daemon.purge import purge_old_captures

    old_ts = (datetime.now(UTC) - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S.%f")

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text) "
            "VALUES (?, 'App', 'Win', NULL, '')",
            (old_ts,),
        )
        await conn.commit()

    purged = await purge_old_captures(months=12, chroma_store=None)
    assert purged == 1


# ── sweep_orphaned_screenshots ───────────────────────────────────────────────


async def test_sweep_deletes_only_old_unreferenced_screenshot_files(tmp_home):
    import os
    import time as _time

    from brn_daemon.purge import sweep_orphaned_screenshots

    await init_db()
    shots = get_brn_home() / "screenshots" / "2026" / "06" / "01"
    shots.mkdir(parents=True, exist_ok=True)

    referenced = shots / "kept.jpg"
    referenced.write_bytes(b"fake")
    old_orphan = shots / "orphan.jpg"
    old_orphan.write_bytes(b"fake")
    old_orphan_enc = shots / "orphan.jpg.enc"
    old_orphan_enc.write_bytes(b"fake")
    fresh_orphan = shots / "inflight.jpg"
    fresh_orphan.write_bytes(b"fake")
    not_a_screenshot = shots / "notes.txt"
    not_a_screenshot.write_bytes(b"keep me")

    # Age everything except the fresh orphan past the safety window
    stale = _time.time() - 7200
    for p in (referenced, old_orphan, old_orphan_enc, not_a_screenshot):
        os.utime(p, (stale, stale))

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES (?, 'heartbeat', ?)",
            (datetime.now(UTC).isoformat(), str(referenced)),
        )
        await conn.commit()

    deleted = await sweep_orphaned_screenshots(min_age_seconds=3600)

    assert deleted == 2
    assert referenced.exists()          # in the DB → kept
    assert not old_orphan.exists()      # old + unreferenced → swept
    assert not old_orphan_enc.exists()  # encrypted orphan → swept
    assert fresh_orphan.exists()        # too young → kept (in-flight safety)
    assert not_a_screenshot.exists()    # wrong suffix → never touched


async def test_sweep_handles_missing_screenshots_dir(tmp_home):
    from brn_daemon.purge import sweep_orphaned_screenshots

    await init_db()
    assert await sweep_orphaned_screenshots() == 0
