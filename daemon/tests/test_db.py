from datetime import UTC

import aiosqlite
import pytest

from brn_daemon.db import get_db_path, init_db


async def test_init_db_creates_all_tables(tmp_home):
    await init_db()
    import aiosqlite
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
    assert tables == {
        "activities", "app_exclusions", "captures", "journals", "blog_posts",
        "user_instructions", "plugins", "plugin_rules", "plugin_rule_executions",
        "shared_notes", "devices",
    }

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

    from brn_daemon.db import get_db_path, init_db
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

    from brn_daemon.db import get_db_path, init_db
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
    from datetime import datetime
    now = datetime.now(UTC).isoformat()
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

async def test_plugins_name_unique(db):
    await db.execute("INSERT INTO plugins (name, command) VALUES ('joplin', 'node')")
    await db.commit()
    import aiosqlite
    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute("INSERT INTO plugins (name, command) VALUES ('joplin', 'other')")
        await db.commit()


async def test_plugin_rules_cascade_delete(db):
    await db.execute("INSERT INTO plugins (name, command) VALUES ('p1', 'node')")
    await db.commit()
    cur = await db.execute("SELECT id FROM plugins WHERE name = 'p1'")
    pid = (await cur.fetchone())[0]
    await db.execute(
        "INSERT INTO plugin_rules (plugin_id, title, rule_text, trigger) VALUES (?, 't', 'r', 'manual')",
        (pid,),
    )
    await db.commit()
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("DELETE FROM plugins WHERE id = ?", (pid,))
    await db.commit()
    cur = await db.execute("SELECT COUNT(*) FROM plugin_rules WHERE plugin_id = ?", (pid,))
    assert (await cur.fetchone())[0] == 0


async def test_plugin_rule_executions_cascade_delete(db):
    await db.execute("INSERT INTO plugins (name, command) VALUES ('p1', 'node')")
    await db.commit()
    cur = await db.execute("SELECT id FROM plugins WHERE name = 'p1'")
    pid = (await cur.fetchone())[0]
    await db.execute(
        "INSERT INTO plugin_rules (plugin_id, title, rule_text, trigger) VALUES (?, 't', 'r', 'manual')",
        (pid,),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM plugin_rules")
    rid = (await cur.fetchone())[0]
    await db.execute(
        "INSERT INTO plugin_rule_executions (rule_id, started_at, status) VALUES (?, datetime('now'), 'ok')",
        (rid,),
    )
    await db.commit()
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("DELETE FROM plugin_rules WHERE id = ?", (rid,))
    await db.commit()
    cur = await db.execute("SELECT COUNT(*) FROM plugin_rule_executions WHERE rule_id = ?", (rid,))
    assert (await cur.fetchone())[0] == 0


async def test_activities_has_app_name_override_column(tmp_home):
    await init_db()
    import aiosqlite

    from brn_daemon.db import get_db_path
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute("PRAGMA table_info(activities)")
        columns = {row[1] for row in await cursor.fetchall()}
    assert "app_name_override" in columns


async def test_init_db_is_idempotent(tmp_home):
    """Running init_db twice must not raise — migrations must be safe to re-apply."""
    from brn_daemon.db import init_db
    await init_db()
    await init_db()  # second call: ALTER TABLE would fail if not caught correctly


async def test_activity_filter_indexes_exist(tmp_home, db):
    """task_category and productivity_state indexes must exist after init_db."""
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='activities'"
    )
    rows = await cur.fetchall()
    index_names = {r[0] for r in rows}
    assert "idx_activities_task_category" in index_names
    assert "idx_activities_productivity_state" in index_names


async def test_activities_cascade_delete(tmp_home, db):
    """Deleting a capture must cascade-delete its activity."""
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute(
        "INSERT INTO captures (captured_at, app_name) VALUES ('2024-01-01T10:00:00', 'TestApp')"
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    row = await cur.fetchone()
    capture_id = row[0]

    await db.execute(
        "INSERT INTO activities (capture_id, started_at, summary) VALUES (?, '2024-01-01T10:00:00', 'test')",
        (capture_id,),
    )
    await db.commit()

    await db.execute("DELETE FROM captures WHERE id = ?", (capture_id,))
    await db.commit()

    cur = await db.execute("SELECT COUNT(*) FROM activities WHERE capture_id = ?", (capture_id,))
    row = await cur.fetchone()
    assert row[0] == 0, "activity should have been cascade-deleted"


async def test_init_db_creates_shared_notes_table(tmp_home):
    """shared_notes table and its index exist after init_db."""
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shared_notes'"
        )
        assert await cur.fetchone() is not None, "shared_notes table missing"

        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_shared_notes_created_at'"
        )
        assert await cur.fetchone() is not None, "idx_shared_notes_created_at index missing"


async def test_init_db_idempotent_with_shared_notes(tmp_home):
    """Calling init_db twice must not raise (IF NOT EXISTS guards)."""
    await init_db()
    await init_db()


async def test_init_db_drops_legacy_ended_at_column(tmp_home):
    """A DB created by an older schema (with activities.ended_at) is migrated."""
    import aiosqlite

    from brn_daemon.db import get_db_path

    # Build the schema fresh, then re-add the legacy column to simulate an old DB.
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("ALTER TABLE activities ADD COLUMN ended_at DATETIME")
        await conn.commit()

    await init_db()

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT 1 FROM pragma_table_info('activities') WHERE name = 'ended_at'"
        )
        assert await cur.fetchone() is None, "ended_at should have been dropped"


async def test_fresh_schema_has_no_ended_at(tmp_home):
    import aiosqlite

    from brn_daemon.db import get_db_path

    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT 1 FROM pragma_table_info('activities') WHERE name = 'ended_at'"
        )
        assert await cur.fetchone() is None
