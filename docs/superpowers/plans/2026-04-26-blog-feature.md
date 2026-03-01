# Blog Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Blog section to 2brn that auto-generates a daily public-facing dev log from activity summaries, the existing journal, and Joplin notes — parallel to the existing Journal section, with AI-driven company-data filtering.

**Architecture:** New `blog.py` module (mirrors `journal.py`) with `BlogGenerator` + `BlogMirror` classes. New `routes/blog.py` FastAPI router (3 endpoints). New `Blog.tsx` React component (mirrors `Journal.tsx`). The `blog_posts` SQLite table is added to `init_db()` with no migration script needed. All existing Journal code is untouched.

**Tech Stack:** Python 3.12 / FastAPI / aiosqlite / APScheduler (daemon); React 19 / TypeScript / TanStack Query v5 / Tailwind v3 (UI); Joplin Web Clipper API (mirror); JLL GPT Gateway (LLM generation)

---

## Task 1: Add `blog_posts` table to SQLite schema

**Files:**
- Modify: `daemon/src/brn_daemon/db.py`
- Test: `daemon/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Add to `daemon/tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd daemon && uv run --extra dev pytest tests/test_db.py::test_blog_posts_table_exists tests/test_db.py::test_blog_posts_unique_date -v
```

Expected: FAIL — `blog_posts` table does not exist yet.

- [ ] **Step 3: Add `blog_posts` table to `init_db()`**

In `daemon/src/brn_daemon/db.py`, inside the `executescript` string in `init_db()`, add after the `app_exclusions` table and before the `CREATE INDEX` lines:

```python
            CREATE TABLE IF NOT EXISTS blog_posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                date           TEXT NOT NULL,
                content        TEXT,
                generated_at   TEXT NOT NULL,
                edited_by_user INTEGER NOT NULL DEFAULT 0,
                UNIQUE(date)
            );
```

Also add an index after the existing index definitions:

```python
            CREATE INDEX IF NOT EXISTS idx_blog_posts_date ON blog_posts(date);
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd daemon && uv run --extra dev pytest tests/test_db.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/db.py daemon/tests/test_db.py
git commit -m "feat(db): add blog_posts table to init_db schema"
```

---

## Task 2: Add blog config fields

**Files:**
- Modify: `daemon/src/brn_daemon/config.py`
- Test: `daemon/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `daemon/tests/test_config.py`:

```python
def test_config_blog_defaults(tmp_home):
    from brn_daemon.config import load_config
    cfg = load_config()
    assert cfg.blog_generation_time == "21:30"
    assert cfg.blog_mirror_enabled is True

def test_config_blog_fields_persist(tmp_home):
    from brn_daemon.config import load_config, save_config
    cfg = load_config()
    cfg.blog_generation_time = "22:00"
    cfg.blog_mirror_enabled = False
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_generation_time == "22:00"
    assert loaded.blog_mirror_enabled is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd daemon && uv run --extra dev pytest tests/test_config.py::test_config_blog_defaults tests/test_config.py::test_config_blog_fields_persist -v
```

Expected: FAIL — `Config` has no `blog_generation_time` attribute.

- [ ] **Step 3: Add fields to `Config` dataclass and `load_config`/`save_config`**

In `daemon/src/brn_daemon/config.py`, add to the `Config` dataclass after `excluded_apps`:

```python
    blog_generation_time: str = "21:30"   # HH:MM, 24-hour
    blog_mirror_enabled: bool = True       # Mirror posts to Joplin "Blog Posts" notebook
```

In `load_config()`, add to the `Config(...)` constructor call:

```python
            blog_generation_time=data.get("blog_generation_time", DEFAULT_CONFIG.blog_generation_time),
            blog_mirror_enabled=data.get("blog_mirror_enabled", DEFAULT_CONFIG.blog_mirror_enabled),
```

In `save_config()`, add to the `data` dict:

```python
        "blog_generation_time": cfg.blog_generation_time,
        "blog_mirror_enabled": cfg.blog_mirror_enabled,
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd daemon && uv run --extra dev pytest tests/test_config.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/config.py daemon/tests/test_config.py
git commit -m "feat(config): add blog_generation_time and blog_mirror_enabled fields"
```

---

## Task 3: Implement `BlogGenerator` and `BlogMirror`

**Files:**
- Create: `daemon/src/brn_daemon/blog.py`
- Create: `daemon/tests/test_blog.py`

- [ ] **Step 1: Write the failing tests**

Create `daemon/tests/test_blog.py`:

```python
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
    # Should still produce a valid prompt, not crash
    assert isinstance(prompt, str)


# ── BlogGenerator.generate ─────────────────────────────────────────────────────

async def test_blog_generator_creates_post(db, tmp_home):
    gateway = MagicMock()
    gateway.chat_complete = AsyncMock(return_value="## April 26 — Dev Log\n\nBuilt the blog feature today.")

    gen = BlogGenerator(gateway=gateway)
    result = await gen.generate(target_date=date(2026, 4, 26))

    assert result == "## April 26 — Dev Log\n\nBuilt the blog feature today."

    # Verify it was saved to the DB
    async with aiosqlite.connect(db.get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM blog_posts WHERE date = ?", ("2026-04-26",))
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == "## April 26 — Dev Log\n\nBuilt the blog feature today."
    assert row[1] == 0


async def test_blog_generator_skips_if_edited_by_user(db, tmp_home):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Pre-insert a post marked as edited by user
    async with aiosqlite.connect(db.get_db_path()) as conn:
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
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Insert a capture + activity for the test date
    async with aiosqlite.connect(db.get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, trigger) VALUES (?, ?, ?, ?)",
            ("2026-04-26T10:00:00+00:00", "VS Code", "blog.py — 2brn", "heartbeat")
        )
        capture_id = (await conn.execute("SELECT last_insert_rowid()")).fetchone
        await conn.execute(
            """INSERT INTO activities (capture_id, started_at, summary, task_category, productivity_state)
               VALUES (1, '2026-04-26T10:00:00+00:00', 'Implementing BlogGenerator class', 'creative', 'focused')"""
        )
        await conn.commit()

    gateway = MagicMock()
    gateway.chat_complete = AsyncMock(return_value="Dev log content")

    gen = BlogGenerator(gateway=gateway)
    await gen.generate(target_date=date(2026, 4, 26))

    # Verify chat_complete was called with a prompt containing the activity
    call_args = gateway.chat_complete.call_args[0][0]
    user_msg = next(m["content"] for m in call_args if m["role"] == "user")
    assert "BlogGenerator" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd daemon && uv run --extra dev pytest tests/test_blog.py -v
```

Expected: FAIL — `brn_daemon.blog` module does not exist.

- [ ] **Step 3: Create `daemon/src/brn_daemon/blog.py`**

```python
import logging
import aiosqlite
from datetime import date, datetime, timezone
from pathlib import Path

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

BLOG_SYSTEM_PROMPT = """You are a technical writer helping a software engineer maintain a public dev log.
Given a day's activities, journal entry, and notes — write a concise dev log \
entry in first person. Focus on: what was learned, what was built, what was \
tried or experimented with.

Write for a public technical audience. Use a direct, honest, personal tone.
Structure: a short narrative opening, then **What I learned**, **What I built**, \
**Experimenting with** sections as applicable. Only include sections with content.

IMPORTANT: This is a public blog. Omit anything company-confidential — \
client names, internal system names, proprietary business logic, employer-specific \
work tasks, or anything that could identify a client or employer's internal \
systems. If an activity is purely corporate work with no public learning value, \
skip it entirely. Personal projects, open-source tools, technical learnings, \
and experiments are all fair game."""


def build_blog_prompt(
    target_date: str,
    summaries: list[str],
    journal_content: str | None,
    joplin_notes: list[tuple[str, str]],  # list of (title, body)
) -> str:
    parts = [f"Date: {target_date}"]

    if summaries:
        parts.append("\n## Activities\n" + "\n".join(f"- {s}" for s in summaries))
    else:
        parts.append("\n## Activities\nNo recorded activities for this day.")

    if journal_content:
        parts.append(f"\n## Journal Entry\n{journal_content}")

    if joplin_notes:
        notes_text = "\n\n".join(f"### {title}\n{body[:600]}" for title, body in joplin_notes)
        parts.append(f"\n## Notes from the day\n{notes_text}")

    parts.append("\n\nWrite the dev log entry.")
    return "\n".join(parts)


class BlogGenerator:
    def __init__(self, gateway):
        self._gateway = gateway

    async def generate(self, target_date: date) -> str | None:
        date_str = target_date.isoformat()

        async with aiosqlite.connect(get_db_path()) as conn:
            # Guard: skip if user has edited this post
            cur = await conn.execute(
                "SELECT id, edited_by_user FROM blog_posts WHERE date = ?", (date_str,)
            )
            existing = await cur.fetchone()
            if existing and existing[1] == 1:
                logger.info("Blog post for %s was edited by user — skipping", date_str)
                return None

            # Fetch activity summaries for the day
            cur = await conn.execute(
                "SELECT summary FROM activities "
                "WHERE started_at >= ? AND started_at <= ? "
                "AND summary IS NOT NULL AND summary != '' "
                "ORDER BY started_at",
                (f"{date_str}T00:00:00", f"{date_str}T23:59:59.999999"),
            )
            rows = await cur.fetchall()
            summaries = [r[0] for r in rows]

            # Fetch journal content for the day (full-day entry, label IS NULL)
            cur = await conn.execute(
                "SELECT content FROM journals WHERE date = ? AND label IS NULL", (date_str,)
            )
            journal_row = await cur.fetchone()
            journal_content = journal_row[0] if journal_row else None

        # Fetch Joplin notes modified on target_date (read-only, Joplin SQLite)
        joplin_notes = _fetch_joplin_notes_for_date(target_date)

        prompt = build_blog_prompt(date_str, summaries, journal_content, joplin_notes)
        content = await self._gateway.chat_complete([
            {"role": "system", "content": BLOG_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])

        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                """INSERT INTO blog_posts (date, content, generated_at, edited_by_user)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(date) DO UPDATE SET
                     content = excluded.content,
                     generated_at = excluded.generated_at
                   WHERE edited_by_user = 0""",
                (date_str, content, now),
            )
            await conn.commit()

        return content


def _fetch_joplin_notes_for_date(target_date: date) -> list[tuple[str, str]]:
    """Read Joplin notes modified on target_date from Joplin's SQLite (read-only).
    Returns list of (title, body). Falls back to [] if Joplin DB is not accessible."""
    import sqlite3
    from pathlib import Path

    joplin_db = Path.home() / ".config" / "joplin-desktop" / "database.sqlite"
    if not joplin_db.exists():
        return []

    # Joplin stores updated_time as Unix milliseconds
    import datetime as _dt
    day_start_ms = int(_dt.datetime(
        target_date.year, target_date.month, target_date.day,
        tzinfo=_dt.timezone.utc
    ).timestamp() * 1000)
    day_end_ms = day_start_ms + 86_400_000  # +24h in ms

    try:
        conn = sqlite3.connect(f"file:{joplin_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT title, body FROM notes "
            "WHERE updated_time >= ? AND updated_time < ? "
            "AND is_conflict = 0 AND deleted_time = 0 "
            "ORDER BY updated_time DESC LIMIT 20",
            (day_start_ms, day_end_ms),
        )
        rows = cur.fetchall()
        conn.close()
        return [(r["title"], r["body"] or "") for r in rows if r["title"]]
    except Exception as exc:
        logger.warning("Could not read Joplin notes for blog: %s", exc)
        return []


class BlogMirror:
    """Mirrors blog posts to Joplin via the Web Clipper API.

    Creates/updates a note titled "Blog — YYYY-MM-DD" in the "Blog Posts" notebook.
    Falls back silently if Joplin is not running.
    """

    NOTEBOOK = "Blog Posts"

    def __init__(self, token: str = "", port: int = 41184):
        self._token = token
        self._port = port

    def _api(self, method: str, endpoint: str, body: dict | None = None) -> dict | None:
        import urllib.request
        import urllib.error
        import json as _json
        url = f"http://localhost:{self._port}{endpoint}?token={self._token}"
        data = _json.dumps(body).encode() if body else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return _json.loads(r.read())
        except urllib.error.URLError:
            return None  # Joplin not running — silently skip
        except Exception as exc:
            logger.warning("BlogMirror API error: %s", exc)
            return None

    def _get_or_create_notebook(self) -> str | None:
        result = self._api("GET", "/folders")
        if result is None:
            return None
        for folder in result.get("items", []):
            if folder.get("title") == self.NOTEBOOK:
                return folder["id"]
        created = self._api("POST", "/folders", {"title": self.NOTEBOOK})
        return created["id"] if created else None

    def _find_note(self, title: str) -> str | None:
        import urllib.request
        import urllib.parse
        import json as _json
        params = urllib.parse.urlencode({
            "token": self._token,
            "query": title,
            "fields": "id,title",
        })
        url = f"http://localhost:{self._port}/search?{params}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = _json.loads(r.read())
                for item in data.get("items", []):
                    if item.get("title") == title:
                        return item["id"]
        except Exception:
            pass
        return None

    def mirror(self, target_date: date, content: str) -> None:
        """Create or update a Joplin note for this blog post."""
        note_title = f"Blog — {target_date.isoformat()}"
        note_body = f"# {note_title}\n\n{content}"

        note_id = self._find_note(note_title)
        if note_id:
            self._api("PUT", f"/notes/{note_id}", {"body": note_body})
            logger.info("Updated Joplin blog note '%s'", note_title)
            return

        nb_id = self._get_or_create_notebook()
        payload: dict = {"title": note_title, "body": note_body}
        if nb_id:
            payload["parent_id"] = nb_id
        result = self._api("POST", "/notes", payload)
        if result:
            logger.info("Created Joplin blog note '%s'", note_title)
        else:
            logger.warning("Could not mirror blog to Joplin (app not running?) — skipping")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd daemon && uv run --extra dev pytest tests/test_blog.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/blog.py daemon/tests/test_blog.py
git commit -m "feat(blog): add BlogGenerator, BlogMirror, and build_blog_prompt"
```

---

## Task 4: Add blog API routes

**Files:**
- Create: `daemon/src/brn_daemon/routes/blog_routes.py`

- [ ] **Step 1: Write the failing test**

Add to `daemon/tests/test_blog.py` (append at bottom):

```python
# ── API routes ─────────────────────────────────────────────────────────────────

import pytest
from httpx import AsyncClient, ASGITransport
from brn_daemon.main import create_app


async def test_get_blog_post_404(tmp_home, db):
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/blog/2026-04-26")
    assert resp.status_code == 404


async def test_get_blog_post_returns_post(tmp_home, db):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db.get_db_path()) as conn:
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
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db.get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO blog_posts (date, content, generated_at, edited_by_user) VALUES (?, ?, ?, 0)",
            ("2026-04-26", "Original content", now)
        )
        await conn.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put("/blog/2026-04-26", json={"content": "Edited content"})
    assert resp.status_code == 200

    async with aiosqlite.connect(db.get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM blog_posts WHERE date = ?", ("2026-04-26",))
        row = await cur.fetchone()
    assert row[0] == "Edited content"
    assert row[1] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd daemon && uv run --extra dev pytest tests/test_blog.py::test_get_blog_post_404 tests/test_blog.py::test_get_blog_post_returns_post tests/test_blog.py::test_put_blog_post_sets_edited -v
```

Expected: FAIL — routes not registered yet.

- [ ] **Step 3: Create `daemon/src/brn_daemon/routes/blog_routes.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import aiosqlite
from datetime import datetime, timezone
from brn_daemon.db import get_db_path

router = APIRouter()


class BlogPostResponse(BaseModel):
    date: str
    content: str | None
    generated_at: str | None
    edited_by_user: bool


class BlogPostUpdateRequest(BaseModel):
    content: str


@router.get("/blog/{date}", response_model=BlogPostResponse)
async def get_blog_post(date: str):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT date, content, generated_at, edited_by_user FROM blog_posts WHERE date = ?",
            (date,)
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, f"No blog post for {date}")
    return BlogPostResponse(**dict(row))


@router.post("/blog/{date}/generate")
async def generate_blog_post(date: str):
    from brn_daemon.main import app_state
    gen = app_state.get("blog_generator")
    if not gen:
        raise HTTPException(503, "Blog generator not available")

    generating: set = app_state.setdefault("blog_generating", set())
    if date in generating:
        raise HTTPException(409, f"Blog post for {date} is already being generated")

    generating.add(date)
    try:
        from datetime import date as dt_date
        target = dt_date.fromisoformat(date)
        content = await gen.generate(target_date=target)
    finally:
        generating.discard(date)

    return {"ok": True, "generated": content is not None}


@router.put("/blog/{date}")
async def update_blog_post(date: str, body: BlogPostUpdateRequest):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """INSERT INTO blog_posts (date, content, generated_at, edited_by_user)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(date) DO UPDATE SET
                 content = excluded.content,
                 edited_by_user = 1""",
            (date, body.content, now)
        )
        await conn.commit()
    return {"ok": True}
```

- [ ] **Step 4: Wire the router and `BlogGenerator` into `main.py`**

In `daemon/src/brn_daemon/main.py`:

Add import at top with other imports:
```python
from brn_daemon.blog import BlogGenerator, BlogMirror
```

In `app_state` dict, add after `"journal_generating": set()`:
```python
    "blog_generator": None,
    "blog_generating": set(),
```

In the `lifespan` function, after `journal_gen = JournalGenerator(gateway=gateway)`:
```python
    blog_gen = BlogGenerator(gateway=gateway)
    blog_mirror = BlogMirror(token=get_gateway_token() or "")
    app_state["blog_generator"] = blog_gen
```

In the `scheduler` section, after the `purge_daily` job:
```python
    # 21:30: daily blog post generation
    _blog_hour, _blog_minute = (int(x) for x in cfg.blog_generation_time.split(":"))
    scheduler.add_job(
        lambda: asyncio.create_task(_generate_and_mirror_blog(
            blog_gen, blog_mirror, dt_date.today()
        )),
        "cron", hour=_blog_hour, minute=_blog_minute, id="blog_daily"
    )
```

Add the helper function after `_generate_and_mirror`:
```python
async def _generate_and_mirror_blog(
    blog_gen: BlogGenerator,
    blog_mirror: BlogMirror,
    target_date: dt_date,
) -> None:
    from brn_daemon.config import load_config
    content = await blog_gen.generate(target_date=target_date)
    cfg = load_config()
    if content and cfg.blog_mirror_enabled:
        blog_mirror.mirror(target_date, content)
```

In `create_app()`, add the blog router import and registration:
```python
    from brn_daemon.routes import blog_routes
    ...
    app.include_router(blog_routes.router)
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
cd daemon && uv run --extra dev pytest tests/test_blog.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add daemon/src/brn_daemon/routes/blog_routes.py daemon/src/brn_daemon/main.py
git commit -m "feat(blog): add blog API routes and wire BlogGenerator into daemon"
```

---

## Task 5: Update settings API to include blog fields

**Files:**
- Modify: `daemon/src/brn_daemon/routes/settings_routes.py`

- [ ] **Step 1: Update `SettingsResponse` and `SettingsUpdateRequest`**

In `daemon/src/brn_daemon/routes/settings_routes.py`:

Add to `SettingsResponse`:
```python
    blog_generation_time: str
    blog_mirror_enabled: bool
```

Add to `SettingsUpdateRequest`:
```python
    blog_generation_time: str | None = None
    blog_mirror_enabled: bool | None = None
```

Update `get_settings()` return to include:
```python
        blog_generation_time=cfg.blog_generation_time,
        blog_mirror_enabled=cfg.blog_mirror_enabled,
```

Update `update_settings()` to handle the new fields (add after `purge_months` block):
```python
    if body.blog_generation_time is not None:
        cfg.blog_generation_time = body.blog_generation_time
    if body.blog_mirror_enabled is not None:
        cfg.blog_mirror_enabled = body.blog_mirror_enabled
```

- [ ] **Step 2: Run existing tests to verify nothing broke**

```bash
cd daemon && uv run --extra dev pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add daemon/src/brn_daemon/routes/settings_routes.py
git commit -m "feat(settings): expose blog_generation_time and blog_mirror_enabled in settings API"
```

---

## Task 6: Add `BlogPost` type and API functions to frontend

**Files:**
- Modify: `ui/src/api/types.ts`
- Modify: `ui/src/api/client.ts`
- Modify: `ui/src/api/queryKeys.ts`

- [ ] **Step 1: Add `BlogPost` interface to `types.ts`**

In `ui/src/api/types.ts`, add after the `JournalEntry` interface:

```typescript
export interface BlogPost {
  date: string
  content: string | null
  generated_at: string | null
  edited_by_user: boolean
}
```

Also update `AppSettings` to include blog fields (add after `has_token: boolean`):
```typescript
  blog_generation_time: string
  blog_mirror_enabled: boolean
```

- [ ] **Step 2: Add blog API functions to `client.ts`**

In `ui/src/api/client.ts`, add to the imports:
```typescript
import type {
  DaemonStatus, CaptureRecord, ActivityRecord, JournalEntry, BlogPost,
  DailyInsights, AppSettings, AppExclusion, LogLine, DebugStatus
} from './types'
```

Add to the `api` object after `updateJournal`:
```typescript
  getBlogPost: (date: string) => get<BlogPost>(`/blog/${date}`).catch(e => {
    if (e.message.includes('404')) return null
    throw e
  }),
  generateBlogPost: (date: string) => post<{ ok: boolean; generated: boolean }>(`/blog/${date}/generate`),
  updateBlogPost: (date: string, content: string) => put<{ ok: boolean }>(`/blog/${date}`, { content }),
```

- [ ] **Step 3: Add blog query key to `queryKeys.ts`**

In `ui/src/api/queryKeys.ts`, add after `journal`:
```typescript
  blog: (date: string) => ['blog', date] as const,
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd ui && nvm --version && pnpm exec tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/api/types.ts ui/src/api/client.ts ui/src/api/queryKeys.ts
git commit -m "feat(ui): add BlogPost type, blog API functions, and blog query key"
```

---

## Task 7: Create `Blog.tsx` component

**Files:**
- Create: `ui/src/components/Blog.tsx`

- [ ] **Step 1: Create `Blog.tsx`**

Create `ui/src/components/Blog.tsx`:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import MarkdownRenderer from './shared/MarkdownRenderer'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

type BtnVariant = 'ghost' | 'primary' | 'danger'
const btnStyles: Record<BtnVariant, React.CSSProperties> = {
  ghost:   { background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' },
  primary: { background: 'var(--accent)',        color: '#fff',              border: 'none' },
  danger:  { background: 'var(--red-bg)',        color: 'var(--red)',         border: '1px solid rgba(248,113,113,0.2)' },
}

function Btn({
  onClick, disabled, children, variant = 'ghost',
}: {
  onClick?: () => void
  disabled?: boolean
  children: React.ReactNode
  variant?: BtnVariant
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all duration-150 disabled:opacity-40"
      style={btnStyles[variant]}
    >
      {children}
    </button>
  )
}

export default function Blog() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [editing, setEditing]           = useState(false)
  const [editContent, setEditContent]   = useState('')
  const qc = useQueryClient()

  const { data: post } = useQuery({
    queryKey: queryKeys.blog(selectedDate),
    queryFn:  () => api.getBlogPost(selectedDate),
    throwOnError: false,
    retry: false,
  })

  const generateMutation = useMutation({
    mutationFn: () => api.generateBlogPost(selectedDate),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.blog(selectedDate) }),
  })

  const saveMutation = useMutation({
    mutationFn: (content: string) => api.updateBlogPost(selectedDate, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.blog(selectedDate) })
      setEditing(false)
    },
  })

  const handleDateChange = (date: string) => {
    setSelectedDate(date)
    setEditing(false)
    setEditContent('')
  }

  return (
    <div className="page-enter p-7 max-w-[760px] mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-[19px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            Blog
          </h1>
          {post?.edited_by_user && (
            <span
              className="text-[11px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: 'var(--amber-bg)', color: 'var(--amber)' }}
            >
              edited
            </span>
          )}
        </div>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => handleDateChange(e.target.value)}
          className="rounded-[9px] px-3 py-1.5 text-[13px] border outline-none font-mono"
          style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)', color: 'var(--text)' }}
        />
      </div>

      {/* Error banners */}
      {generateMutation.isError && (
        <div className="mb-4 px-4 py-3 rounded-[9px] text-[13px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}>
          Failed to generate blog post.
        </div>
      )}
      {saveMutation.isError && (
        <div className="mb-4 px-4 py-3 rounded-[9px] text-[13px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}>
          Failed to save changes.
        </div>
      )}

      {/* States */}
      {!post ? (
        <div
          className="rounded-[12px] border p-10 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <div className="text-4xl mb-4 opacity-20">✍️</div>
          <p className="text-[14px] mb-5" style={{ color: 'var(--text-muted)' }}>
            No blog post for {selectedDate}
          </p>
          <Btn variant="primary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
            {generateMutation.isPending ? 'Generating…' : 'Generate Post'}
          </Btn>
        </div>

      ) : editing ? (
        <div className="space-y-3">
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            rows={22}
            className="w-full rounded-[12px] border px-4 py-3 text-[14px] font-mono resize-none outline-none"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border-2)',
              color: 'var(--text)',
              lineHeight: 1.7,
            }}
          />
          <div className="flex justify-end gap-2">
            <Btn onClick={() => setEditing(false)}>Cancel</Btn>
            <Btn variant="primary" onClick={() => saveMutation.mutate(editContent)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </Btn>
          </div>
        </div>

      ) : (
        <div
          className="rounded-[12px] border p-6"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <MarkdownRenderer content={post.content ?? ''} />
          <div className="flex gap-2 mt-6 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <Btn onClick={() => { setEditing(true); setEditContent(post.content ?? '') }}>Edit</Btn>
            {!post.edited_by_user && (
              <Btn onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
                {generateMutation.isPending ? 'Regenerating…' : 'Regenerate'}
              </Btn>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd ui && nvm --version && pnpm exec tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/Blog.tsx
git commit -m "feat(ui): add Blog component with calendar, markdown view, edit, and generate"
```

---

## Task 8: Wire Blog into App.tsx sidebar and router

**Files:**
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Add Blog import, nav entry, and route**

In `ui/src/App.tsx`:

Add import after the `Journal` import:
```tsx
import Blog from './components/Blog'
```

In the `NAV` array, add after the Journal entry:
```tsx
  { to: '/blog',     label: 'Blog',     icon: '✍' },
```

In the `<Routes>` block, add after the journal route:
```tsx
<Route path="/blog" element={<Blog />} />
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd ui && nvm --version && pnpm exec tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/App.tsx
git commit -m "feat(ui): add Blog nav item and route to App"
```

---

## Task 9: Add Blog section to Settings UI

**Files:**
- Modify: `ui/src/components/Settings.tsx`

- [ ] **Step 1: Read the existing Settings component to find where to add the Blog section**

Read `ui/src/components/Settings.tsx` and locate the last settings section (it ends before the closing `</div>` of the form). Find the exact pattern used for other input sections (e.g. capture interval or gateway URL).

- [ ] **Step 2: Add Blog settings state and UI**

In `ui/src/components/Settings.tsx`, add two new state fields alongside existing settings state (matching how `captureInterval`, `purgeMonths` etc. are handled):

```tsx
const [blogTime, setBlogTime] = useState(settings?.blog_generation_time ?? '21:30')
const [blogMirror, setBlogMirror] = useState(settings?.blog_mirror_enabled ?? true)
```

Include these in the save handler (wherever `updateSettings` is called, add):
```tsx
blog_generation_time: blogTime,
blog_mirror_enabled: blogMirror,
```

Add a Blog section in the UI (place it after the last existing section, before the save button):

```tsx
{/* Blog */}
<div className="rounded-[12px] border p-5" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
  <h2 className="text-[14px] font-semibold mb-4" style={{ color: 'var(--text)' }}>Blog</h2>
  <div className="space-y-4">
    <div>
      <label className="block text-[12px] mb-1.5 font-medium uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
        Daily generation time
      </label>
      <input
        type="time"
        value={blogTime}
        onChange={e => setBlogTime(e.target.value)}
        className="rounded-[9px] px-3 py-1.5 text-[13px] border outline-none font-mono"
        style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)', color: 'var(--text)' }}
      />
      <p className="text-[12px] mt-1" style={{ color: 'var(--text-dim)' }}>
        24-hour format. Post generates after the evening journal (default 21:30).
      </p>
    </div>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>Mirror to Joplin</p>
        <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>Save blog posts to "Blog Posts" notebook</p>
      </div>
      <button
        onClick={() => setBlogMirror(v => !v)}
        className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
        style={{ background: blogMirror ? 'var(--accent)' : 'var(--bg-surface-2)' }}
      >
        <span
          className="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
          style={{ transform: blogMirror ? 'translateX(24px)' : 'translateX(4px)' }}
        />
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd ui && nvm --version && pnpm exec tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/Settings.tsx
git commit -m "feat(ui): add Blog settings section for generation time and Joplin mirror toggle"
```

---

## Task 10: Smoke test the full feature end-to-end

- [ ] **Step 1: Run the full daemon test suite**

```bash
cd daemon && uv run --extra dev pytest tests/ -v
```

Expected: All tests PASS. Note the total count (should be 42+ original + new blog tests).

- [ ] **Step 2: Start the daemon and verify blog endpoints work**

```bash
cd daemon && uv run python -m brn_daemon.main &
sleep 3

# Verify 404 for missing post
curl -s http://127.0.0.1:7842/blog/2026-04-26
# Expected: {"detail":"No blog post for 2026-04-26"}

# Trigger manual generation
curl -s -X POST http://127.0.0.1:7842/blog/2026-04-26/generate
# Expected: {"ok":true,"generated":true} (or false if no activities/gateway unavailable)

# Verify settings include blog fields
curl -s http://127.0.0.1:7842/settings | python3 -m json.tool | grep blog
# Expected: "blog_generation_time": "21:30", "blog_mirror_enabled": true

# Kill daemon
kill %1
```

- [ ] **Step 3: Start the UI and verify Blog nav and component**

```bash
cd ui && nvm --version && pnpm electron:dev
```

Check:
- "✍ Blog" appears in sidebar after "Journal"
- Clicking Blog shows the Blog component with date picker
- Selecting today shows empty state with "Generate Post" button
- Clicking "Generate Post" calls the API and shows the result
- "Edit" button switches to textarea; saving updates the post and shows "edited" badge
- Settings page shows Blog section with time input and Joplin toggle

- [ ] **Step 4: Final commit**

```bash
git add -A
git status  # verify only expected files remain
git commit -m "feat(blog): complete blog feature — generator, routes, UI, settings"
```

---

## Self-Review Notes

- `db.get_db_path()` is called as a function in tests (via `aiosqlite.connect(db.get_db_path())`). In the actual test fixture, `db` is the aiosqlite connection; use `get_db_path()` directly from the import instead.
- The `test_blog_generator_uses_activities` test uses `lastrowid` via `(await conn.execute("SELECT last_insert_rowid()")).fetchone` — this will not work as written. Simplify: just hard-code `capture_id = 1` in the activity insert since it's the first insert in a fresh `tmp_home` DB.
- `BlogMirror.mirror()` is synchronous (uses `urllib`, not async) — same as `JournalMirror.append_to_daily_note()`. Call it without `await` in `_generate_and_mirror_blog`.
- `create_app()` in tests — the `lifespan` context sets up `app_state["blog_generator"]`. Route tests that call `POST /blog/{date}/generate` need the generator in `app_state`. Use `app_state["blog_generator"] = BlogGenerator(gateway=mock_gateway)` setup in those tests, or test generate via direct unit test instead of the HTTP layer.
