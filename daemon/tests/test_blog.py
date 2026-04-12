"""Tests for the blog generator and nightly pipeline.

BlogMirror and the Joplin-coupled prompt parameter were removed when the
Joplin integration moved out of the core daemon into the generic plugin
system. Mirroring is now expressed as a plugin rule that listens for the
``blog_generated`` event.
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import aiosqlite

from brn_daemon.blog import build_blog_prompt, BlogGenerator


# ── build_blog_prompt ──────────────────────────────────────────────────────────

def test_build_blog_prompt_includes_date():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=["Worked on TanStack Query setup"],
        journal_content=None,
    )
    assert "2026-04-26" in prompt


def test_build_blog_prompt_includes_activities():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=["Built blog feature in 2brn", "Fixed Electron titlebar drag"],
        journal_content=None,
    )
    assert "blog feature" in prompt
    assert "titlebar" in prompt


def test_build_blog_prompt_includes_journal():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=[],
        journal_content="Today I felt productive and learned a lot.",
    )
    assert "productive" in prompt


def test_build_blog_prompt_empty_day():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=[],
        journal_content=None,
    )
    assert "2026-04-26" in prompt
    assert isinstance(prompt, str)


# ── BlogGenerator.generate ─────────────────────────────────────────────────────

async def test_blog_generator_creates_post(db, tmp_home):
    from brn_daemon.db import get_db_path
    chat_fn = AsyncMock(return_value="## April 26 — Dev Log\n\nBuilt the blog feature today.")

    gen = BlogGenerator(chat_fn=chat_fn)
    result = await gen.generate(target_date=date(2026, 4, 26))

    assert result == "## April 26 — Dev Log\n\nBuilt the blog feature today."

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM blog_posts WHERE date = ?", ("2026-04-26",))
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == "## April 26 — Dev Log\n\nBuilt the blog feature today."
    assert row[1] == 0


async def test_blog_generator_skips_if_edited_by_user(db, tmp_home):
    from brn_daemon.db import get_db_path
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO blog_posts (date, content, generated_at, edited_by_user) VALUES (?, ?, ?, 1)",
            ("2026-04-26", "My edited post", now)
        )
        await conn.commit()

    chat_fn = AsyncMock(return_value="New generated content")

    gen = BlogGenerator(chat_fn=chat_fn)
    result = await gen.generate(target_date=date(2026, 4, 26))

    assert result is None
    chat_fn.assert_not_called()


async def test_blog_generator_uses_activities(db, tmp_home):
    from brn_daemon.db import get_db_path

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, trigger) VALUES (?, ?, ?, ?)",
            ("2026-04-26T10:00:00+00:00", "VS Code", "blog.py — 2brn", "heartbeat")
        )
        await conn.execute(
            """INSERT INTO activities (capture_id, started_at, summary, task_category, productivity_state)
               VALUES (1, '2026-04-26T10:00:00+00:00', 'Implementing BlogGenerator class', 'creative', 'focused')"""
        )
        await conn.commit()

    chat_fn = AsyncMock(return_value="Dev log content")

    gen = BlogGenerator(chat_fn=chat_fn)
    await gen.generate(target_date=date(2026, 4, 26))

    call_args = chat_fn.call_args[0][0]
    user_msg = next(m["content"] for m in call_args if m["role"] == "user")
    assert "BlogGenerator" in user_msg


# ── API routes ─────────────────────────────────────────────────────────────────

from httpx import AsyncClient, ASGITransport


async def test_get_blog_post_404(tmp_home, db):
    from brn_daemon.main import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/blog/2026-04-26")
    assert resp.status_code == 404


async def test_get_blog_post_returns_post(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.main import create_app
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO blog_posts (date, content, generated_at, edited_by_user) VALUES (?, ?, ?, 0)",
            ("2026-04-26", "My dev log", now)
        )
        await conn.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/blog/2026-04-26")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "My dev log"
    assert data["edited_by_user"] is False


async def test_put_blog_post_sets_edited(tmp_home, db):
    from brn_daemon.db import get_db_path
    from brn_daemon.main import create_app
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO blog_posts (date, content, generated_at, edited_by_user) VALUES (?, ?, ?, 0)",
            ("2026-04-26", "Original content", now)
        )
        await conn.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put("/blog/2026-04-26", json={"content": "Edited content"})
    assert resp.status_code == 200

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM blog_posts WHERE date = ?", ("2026-04-26",))
        row = await cur.fetchone()
    assert row[0] == "Edited content"
    assert row[1] == 1


# ── _journal_job / _blog_job event firing ──────────────────────────────────────

async def test_split_jobs_fire_journal_and_blog_events(tmp_home, db):
    """Journal job fires journal_generated event; blog job fires blog_generated event."""
    from brn_daemon.main import _journal_job, _blog_job
    from brn_daemon.plugins import EventBus, EventNames

    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value="Today I built something great.")
    blog_gen = MagicMock()
    blog_gen.generate = AsyncMock(return_value="## Dev Log\n\nBuilt something.")

    received: list[tuple[str, dict]] = []

    async def listener(name: str, payload: dict) -> None:
        received.append((name, payload))

    bus = EventBus()
    bus.subscribe(EventNames.JOURNAL_GENERATED, listener)
    bus.subscribe(EventNames.BLOG_GENERATED, listener)

    await _journal_job(journal_gen, bus, target_date=date(2026, 4, 26))
    await _blog_job(blog_gen, bus, target_date=date(2026, 4, 26))

    names = [evt[0] for evt in received]
    assert names == [EventNames.JOURNAL_GENERATED, EventNames.BLOG_GENERATED]
    assert received[0][1]["date"] == "2026-04-26"
    assert received[0][1]["journal_content"] == "Today I built something great."
    assert received[1][1]["blog_content"] == "## Dev Log\n\nBuilt something."


async def test_journal_job_skips_event_when_user_edited(tmp_home, db):
    """If journal generator returns None (user edited), no journal_generated event fires; blog still runs."""
    from brn_daemon.main import _journal_job, _blog_job
    from brn_daemon.plugins import EventBus, EventNames

    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value=None)  # user edited — skipped
    blog_gen = MagicMock()
    blog_gen.generate = AsyncMock(return_value="Blog content")

    received: list[str] = []

    async def listener(name: str, payload: dict) -> None:
        received.append(name)

    bus = EventBus()
    bus.subscribe(EventNames.JOURNAL_GENERATED, listener)
    bus.subscribe(EventNames.BLOG_GENERATED, listener)

    await _journal_job(journal_gen, bus, target_date=date(2026, 4, 26))
    await _blog_job(blog_gen, bus, target_date=date(2026, 4, 26))

    assert received == [EventNames.BLOG_GENERATED]
    blog_gen.generate.assert_called_once()
