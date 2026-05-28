import pytest
import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path
from brn_daemon.db import init_db, get_db_path, get_brn_home
from brn_daemon.purge import purge_old_captures


async def test_purge_removes_old_screenshots(tmp_home):
    await init_db()
    screenshots_dir = get_brn_home() / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    old_file = screenshots_dir / "old.jpg"
    old_file.write_bytes(b"fake")
    new_file = screenshots_dir / "new.jpg"
    new_file.write_bytes(b"fake")

    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    new_date = datetime.now(timezone.utc).isoformat()

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
    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
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
    from datetime import datetime, timezone, timedelta
    import aiosqlite
    from brn_daemon.purge import purge_old_captures
    from brn_daemon.db import get_db_path

    cutoff = datetime.now(timezone.utc) - timedelta(days=400)

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
    from datetime import datetime, timezone, timedelta
    import aiosqlite
    from brn_daemon.purge import purge_old_captures
    from brn_daemon.db import get_db_path

    old_ts = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S.%f")

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text) "
            "VALUES (?, 'App', 'Win', NULL, '')",
            (old_ts,),
        )
        await conn.commit()

    purged = await purge_old_captures(months=12, chroma_store=None)
    assert purged == 1
