"""Tests for the shared content generator helpers."""
import pytest
import aiosqlite
from datetime import datetime, timezone


async def test_load_active_instruction_bodies_returns_enabled_only(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.content_generator import load_active_instruction_bodies

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO user_instructions (title, body, enabled, created_at) VALUES (?, ?, 1, datetime('now'))",
            ("t1", "active"),
        )
        await conn.execute(
            "INSERT INTO user_instructions (title, body, enabled, created_at) VALUES (?, ?, 0, datetime('now'))",
            ("t2", "disabled"),
        )
        await conn.commit()

    result = await load_active_instruction_bodies()
    assert result == ["active"]


async def test_load_active_instruction_bodies_empty(tmp_home, db):
    from brn_daemon.content_generator import load_active_instruction_bodies
    assert await load_active_instruction_bodies() == []


async def test_fetch_day_summaries_returns_activities_for_date(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.content_generator import fetch_day_summaries

    date_str = "2026-05-28"
    ts_in = f"{date_str}T10:00:00.000000"
    ts_out = "2026-05-27T10:00:00.000000"

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text) VALUES (?, 'App', 'Win', NULL, '')",
            (ts_in,),
        )
        cap_id = (await (await conn.execute("SELECT last_insert_rowid()")).fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, task_category_confidence, productivity_state, productivity_confidence) VALUES (?, ?, 'good work', '[]', 'work', 0.9, 'productive', 0.9)",
            (cap_id, ts_in),
        )
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text) VALUES (?, 'App', 'Win', NULL, '')",
            (ts_out,),
        )
        cap_id2 = (await (await conn.execute("SELECT last_insert_rowid()")).fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, task_category_confidence, productivity_state, productivity_confidence) VALUES (?, ?, 'yesterday', '[]', 'work', 0.9, 'productive', 0.9)",
            (cap_id2, ts_out),
        )
        await conn.commit()

    result = await fetch_day_summaries(date_str)
    assert result == ["good work"]


async def test_upsert_generated_content_inserts_new(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.content_generator import upsert_generated_content

    await upsert_generated_content("journals", "2026-05-28", "my journal")

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content FROM journals WHERE date = '2026-05-28'")
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == "my journal"


async def test_upsert_generated_content_updates_if_not_user_edited(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.content_generator import upsert_generated_content

    await upsert_generated_content("journals", "2026-05-28", "first")
    await upsert_generated_content("journals", "2026-05-28", "second")

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content FROM journals WHERE date = '2026-05-28'")
        row = await cur.fetchone()
    assert row[0] == "second"


async def test_upsert_generated_content_skips_user_edited(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.content_generator import upsert_generated_content

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO journals (date, content, generated_at, edited_by_user) VALUES ('2026-05-28', 'user text', '2026-05-28T09:00:00', 1)"
        )
        await conn.commit()

    await upsert_generated_content("journals", "2026-05-28", "generated text")

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content FROM journals WHERE date = '2026-05-28'")
        row = await cur.fetchone()
    assert row[0] == "user text", "User-edited content must not be overwritten"
