"""Tests for the journal generator.

JournalMirror and ResumeUpdater were removed when the Joplin integration was
extracted into the generic plugin system. Mirroring a journal entry to Joplin
(or any other notes app) is now expressed as a plugin rule that listens for
the ``journal_generated`` event.
"""

import pytest
import aiosqlite
from unittest.mock import AsyncMock
from datetime import date

from brn_daemon.db import init_db, get_db_path
from brn_daemon.journal import build_journal_prompt, JournalGenerator


# ── build_journal_prompt ──────────────────────────────────────────────────────

def test_build_journal_prompt_includes_summaries():
    summaries = ["Worked on Python code", "Reviewed emails", "Team standup meeting"]
    prompt = build_journal_prompt("2026-04-12", summaries)
    assert "2026-04-12" in prompt
    assert "Python code" in prompt
    assert "emails" in prompt
    assert "standup" in prompt


def test_build_journal_prompt_empty_day():
    prompt = build_journal_prompt("2026-04-12", [])
    assert "2026-04-12" in prompt
    assert "no recorded" in prompt.lower() or "no activities" in prompt.lower() or "unrecorded" in prompt.lower()


# ── JournalGenerator ──────────────────────────────────────────────────────────

async def test_generate_saves_to_db(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger) VALUES ('2026-04-12T10:00:00', 'heartbeat')"
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        cap_id = (await cur.fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
            "task_category_confidence, productivity_state, productivity_confidence) "
            "VALUES (?, '2026-04-12T10:00:00', 'Worked on Python', '[]', 'work', 0.9, 'focused', 0.85)",
            (cap_id,)
        )
        await conn.commit()

    mock_chat_fn = AsyncMock(return_value="Today I wrote Python code and focused deeply.")

    gen = JournalGenerator(chat_fn=mock_chat_fn)
    content = await gen.generate(target_date=date(2026, 4, 12))
    assert content is not None and "Python" in content

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM journals WHERE date = '2026-04-12'")
        row = await cur.fetchone()
    assert row is not None
    assert "Python" in row[0]
    assert row[1] == 0


async def test_generate_skips_if_user_edited(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO journals (date, content, edited_by_user) VALUES ('2026-04-12', 'My edit', 1)"
        )
        await conn.commit()

    mock_chat_fn = AsyncMock(return_value="New content")
    gen = JournalGenerator(chat_fn=mock_chat_fn)
    result = await gen.generate(target_date=date(2026, 4, 12))
    assert result is None

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content FROM journals WHERE date = '2026-04-12'")
        row = await cur.fetchone()
    assert row[0] == "My edit"
    mock_chat_fn.assert_not_called()


async def test_journal_finds_activities_with_naive_timestamps(tmp_home, db):
    """Activities with naive UTC timestamps must be found by date-range query."""
    import aiosqlite
    from datetime import datetime, timezone

    naive_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    date_str = naive_ts[:10]

    async with aiosqlite.connect(tmp_home / "2brn.db") as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text) "
            "VALUES (?, 'App', 'Win', 'x.jpg', 'hello')",
            (naive_ts,),
        )
        cap_id = (await (await conn.execute("SELECT last_insert_rowid()")).fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
            "task_category_confidence, productivity_state, productivity_confidence) "
            "VALUES (?, ?, 'did stuff', '[]', 'work', 0.9, 'productive', 0.9)",
            (cap_id, naive_ts),
        )
        await conn.commit()

    async with aiosqlite.connect(tmp_home / "2brn.db") as conn:
        cur = await conn.execute(
            "SELECT summary FROM activities "
            "WHERE started_at >= ? AND started_at <= ? "
            "AND summary IS NOT NULL",
            (f"{date_str}T00:00:00", f"{date_str}T23:59:59.999999"),
        )
        rows = await cur.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "did stuff"
