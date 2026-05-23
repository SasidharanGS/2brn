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
