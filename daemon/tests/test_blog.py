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
        joplin_notes=[],
    )
    assert "2026-04-26" in prompt

def test_build_blog_prompt_includes_activities():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=["Built blog feature in 2brn", "Fixed Electron titlebar drag"],
        journal_content=None,
        joplin_notes=[],
    )
    assert "blog feature" in prompt
    assert "titlebar" in prompt

def test_build_blog_prompt_includes_journal():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=[],
        journal_content="Today I felt productive and learned a lot.",
        joplin_notes=[],
    )
    assert "productive" in prompt

def test_build_blog_prompt_includes_joplin_notes():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=[],
        journal_content=None,
        joplin_notes=[("TanStack Query Notes", "staleTime controls cache freshness")],
    )
    assert "staleTime" in prompt

def test_build_blog_prompt_empty_day():
    prompt = build_blog_prompt(
        target_date="2026-04-26",
        summaries=[],
        journal_content=None,
        joplin_notes=[],
    )
    assert "2026-04-26" in prompt
    assert isinstance(prompt, str)


# ── BlogGenerator.generate ─────────────────────────────────────────────────────

async def test_blog_generator_creates_post(db, tmp_home):
    from brn_daemon.db import get_db_path
    gateway = MagicMock()
    gateway.chat_complete = AsyncMock(return_value="## April 26 — Dev Log\n\nBuilt the blog feature today.")

    gen = BlogGenerator(gateway=gateway)
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

    gateway = MagicMock()
    gateway.chat_complete = AsyncMock(return_value="New generated content")

    gen = BlogGenerator(gateway=gateway)
    result = await gen.generate(target_date=date(2026, 4, 26))

    assert result is None
    gateway.chat_complete.assert_not_called()


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

    gateway = MagicMock()
    gateway.chat_complete = AsyncMock(return_value="Dev log content")

    gen = BlogGenerator(gateway=gateway)
    await gen.generate(target_date=date(2026, 4, 26))

    call_args = gateway.chat_complete.call_args[0][0]
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
    from datetime import datetime, timezone
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
    from datetime import datetime, timezone
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


# ── _nightly_pipeline sequencing ───────────────────────────────────────────────

async def test_nightly_pipeline_runs_journal_resume_blog_in_order(tmp_home, db):
    """Journal runs first, resume second (receives journal content), blog third."""
    from brn_daemon.main import _nightly_pipeline
    from brn_daemon.journal import JournalMirror, ResumeUpdater
    from brn_daemon.blog import BlogMirror
    from types import SimpleNamespace

    call_order = []

    # Journal generator — returns content
    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value="Today I built something great.")

    # Journal mirror — records call
    journal_mirror = MagicMock(spec=JournalMirror)
    journal_mirror.write_daily_note = MagicMock(side_effect=lambda *a, **kw: call_order.append("journal_mirror"))

    # Resume updater — records call and checks it receives journal content
    resume_updater = MagicMock(spec=ResumeUpdater)
    async def fake_resume_update(content, target_date):
        assert content == "Today I built something great."
        call_order.append("resume_updater")
    resume_updater.update_from_journal = fake_resume_update

    # Blog generator — records call
    blog_gen = MagicMock()
    async def fake_blog_generate(target_date):
        call_order.append("blog_generate")
        return "## Dev Log\n\nBuilt something."
    blog_gen.generate = fake_blog_generate

    # Blog mirror — records call
    blog_mirror = MagicMock(spec=BlogMirror)
    blog_mirror.mirror = MagicMock(side_effect=lambda *a, **kw: call_order.append("blog_mirror"))

    cfg = SimpleNamespace(blog_mirror_enabled=True)

    await _nightly_pipeline(
        journal_gen, journal_mirror, resume_updater,
        blog_gen, blog_mirror, cfg,
        date(2026, 4, 26)
    )

    assert call_order == ["journal_mirror", "resume_updater", "blog_generate", "blog_mirror"]


async def test_nightly_pipeline_skips_resume_and_blog_if_no_journal(tmp_home, db):
    """If journal generation returns None (user edited), resume and blog still run independently."""
    from brn_daemon.main import _nightly_pipeline
    from brn_daemon.journal import JournalMirror, ResumeUpdater
    from brn_daemon.blog import BlogMirror
    from types import SimpleNamespace

    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value=None)  # user edited — skipped

    journal_mirror = MagicMock(spec=JournalMirror)
    journal_mirror.write_daily_note = MagicMock()

    resume_updater = MagicMock(spec=ResumeUpdater)
    resume_updater.update_from_journal = AsyncMock()

    blog_gen = MagicMock()
    blog_gen.generate = AsyncMock(return_value="Blog content")

    blog_mirror = MagicMock(spec=BlogMirror)
    blog_mirror.mirror = MagicMock()

    cfg = SimpleNamespace(blog_mirror_enabled=True)

    await _nightly_pipeline(
        journal_gen, journal_mirror, resume_updater,
        blog_gen, blog_mirror, cfg,
        date(2026, 4, 26)
    )

    # journal was skipped — mirror and resume not called
    journal_mirror.write_daily_note.assert_not_called()
    resume_updater.update_from_journal.assert_not_called()
    # blog still runs regardless
    blog_gen.generate.assert_called_once()
    blog_mirror.mirror.assert_called_once()


async def test_nightly_pipeline_respects_blog_mirror_disabled(tmp_home, db):
    """Blog mirror is skipped when blog_mirror_enabled=False."""
    from brn_daemon.main import _nightly_pipeline
    from brn_daemon.journal import JournalMirror, ResumeUpdater
    from brn_daemon.blog import BlogMirror
    from types import SimpleNamespace

    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value="Journal content")
    journal_mirror = MagicMock(spec=JournalMirror)
    journal_mirror.write_daily_note = MagicMock()
    resume_updater = MagicMock(spec=ResumeUpdater)
    resume_updater.update_from_journal = AsyncMock()
    blog_gen = MagicMock()
    blog_gen.generate = AsyncMock(return_value="Blog content")
    blog_mirror = MagicMock(spec=BlogMirror)
    blog_mirror.mirror = MagicMock()

    cfg = SimpleNamespace(blog_mirror_enabled=False)

    await _nightly_pipeline(
        journal_gen, journal_mirror, resume_updater,
        blog_gen, blog_mirror, cfg,
        date(2026, 4, 26)
    )

    blog_gen.generate.assert_called_once()   # blog is still generated and saved to DB
    blog_mirror.mirror.assert_not_called()   # but NOT mirrored to Joplin
