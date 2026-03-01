import pytest
from brn_daemon.db import init_db, get_db_path

async def test_init_db_creates_all_tables(tmp_home):
    await init_db()
    import aiosqlite
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
    assert tables == {"activities", "app_exclusions", "captures", "journals", "blog_posts"}

async def test_init_db_idempotent(tmp_home):
    await init_db()
    await init_db()
    import aiosqlite
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM captures")
        count = (await cursor.fetchone())[0]
    assert count == 0

async def test_captures_table_schema(db):
    await db.execute(
        "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text, phash, trigger, monitor_index) "
        "VALUES (datetime('now'), 'TestApp', 'Test Window', '/tmp/a.jpg', 'hello', 'abc123', 'heartbeat', 1)"
    )
    await db.commit()
    cursor = await db.execute("SELECT app_name, trigger, monitor_index FROM captures")
    row = await cursor.fetchone()
    assert row == ("TestApp", "heartbeat", 1)


async def test_captures_monitor_index_migration(tmp_home):
    """monitor_index column should be present after init_db(), even on a pre-existing DB."""
    import aiosqlite
    from brn_daemon.db import init_db, get_db_path
    await init_db()
    await init_db()  # second call — migration guard must not fail
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute("PRAGMA table_info(captures)")
        columns = {row[1] for row in await cursor.fetchall()}
    assert "monitor_index" in columns

async def test_activities_table_schema(db):
    await db.execute(
        "INSERT INTO captures (captured_at, trigger) VALUES (datetime('now'), 'heartbeat')"
    )
    await db.commit()
    cursor = await db.execute("SELECT last_insert_rowid()")
    capture_id = (await cursor.fetchone())[0]
    await db.execute(
        "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
        "task_category_confidence, productivity_state, productivity_confidence) "
        "VALUES (?, datetime('now'), 'coding', '[\"python\"]', 'work', 0.9, 'focused', 0.85)",
        (capture_id,)
    )
    await db.commit()
    cursor = await db.execute("SELECT task_category, productivity_state FROM activities")
    row = await cursor.fetchone()
    assert row == ("work", "focused")

async def test_journals_date_unique(db):
    await db.execute("INSERT INTO journals (date, content) VALUES ('2026-04-12', 'Day one')")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute("INSERT INTO journals (date, content) VALUES ('2026-04-12', 'Duplicate')")
        await db.commit()


async def test_journals_schema_has_no_label_column(tmp_home):
    import aiosqlite
    from brn_daemon.db import init_db, get_db_path
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute("PRAGMA table_info(journals)")
        columns = {row[1] for row in await cursor.fetchall()}
    assert "label" not in columns

async def test_app_exclusions_name_unique(db):
    await db.execute("INSERT INTO app_exclusions (app_name) VALUES ('1Password')")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute("INSERT INTO app_exclusions (app_name) VALUES ('1Password')")
        await db.commit()

async def test_blog_posts_table_exists(db):
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='blog_posts'"
    )
    row = await cur.fetchone()
    assert row is not None, "blog_posts table should exist after init_db()"

async def test_blog_posts_unique_date(db):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO blog_posts (date, content, generated_at, edited_by_user) VALUES (?, ?, ?, 0)",
        ("2026-04-26", "First post", now)
    )
    await db.commit()
    # Second insert for same date should raise
    import aiosqlite
    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute(
            "INSERT INTO blog_posts (date, content, generated_at, edited_by_user) VALUES (?, ?, ?, 0)",
            ("2026-04-26", "Duplicate", now)
        )
