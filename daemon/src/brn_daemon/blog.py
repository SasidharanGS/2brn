import asyncio
import logging
import aiosqlite
from datetime import date, datetime, timezone

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

BLOG_SYSTEM_PROMPT = """You are a technical writer helping a software engineer maintain a public dev log.
Given a day's activities, journal entry, and notes — write a concise dev log entry in first person. Focus on: what was learned, what was built, what was tried or experimented with.

Write for a public technical audience. Use a direct, honest, personal tone.
Structure: a short narrative opening, then **What I learned**, **What I built**, **Experimenting with** sections as applicable. Only include sections with content.

IMPORTANT: This is a public blog. Omit anything company-confidential — client names, internal system names, proprietary business logic, employer-specific work tasks, or anything that could identify a client or employer's internal systems. If an activity is purely corporate work with no public learning value, skip it entirely. Personal projects, open-source tools, technical learnings, and experiments are all fair game."""


def build_blog_prompt(
    target_date: str,
    summaries: list[str],
    journal_content: str | None,
    joplin_notes: list[tuple[str, str]],
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
    def __init__(self, chat_fn):
        self._chat_fn = chat_fn

    async def generate(self, target_date: date) -> str | None:
        date_str = target_date.isoformat()

        async with aiosqlite.connect(get_db_path()) as conn:
            cur = await conn.execute(
                "SELECT id, edited_by_user FROM blog_posts WHERE date = ?", (date_str,)
            )
            existing = await cur.fetchone()
            if existing and existing[1] == 1:
                logger.info("Blog post for %s was edited by user — skipping", date_str)
                return None

            cur = await conn.execute(
                "SELECT summary FROM activities "
                "WHERE started_at >= ? AND started_at <= ? "
                "AND summary IS NOT NULL AND summary != '' "
                "ORDER BY started_at",
                (f"{date_str}T00:00:00", f"{date_str}T23:59:59.999999"),
            )
            rows = await cur.fetchall()
            summaries = [r[0] for r in rows]

            cur = await conn.execute(
                "SELECT content FROM journals WHERE date = ?", (date_str,)
            )
            journal_row = await cur.fetchone()
            journal_content = journal_row[0] if journal_row else None

        joplin_notes = await asyncio.get_running_loop().run_in_executor(
            None, _fetch_joplin_notes_for_date, target_date
        )

        prompt = build_blog_prompt(date_str, summaries, journal_content, joplin_notes)
        content = await self._chat_fn([
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
    Falls back to [] if Joplin DB is not accessible."""
    import sqlite3
    from pathlib import Path
    import datetime as _dt

    joplin_db = Path.home() / ".config" / "joplin-desktop" / "database.sqlite"
    if not joplin_db.exists():
        return []

    day_start_ms = int(_dt.datetime(
        target_date.year, target_date.month, target_date.day,
        tzinfo=_dt.timezone.utc
    ).timestamp() * 1000)
    day_end_ms = day_start_ms + 86_400_000

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
            return None
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
