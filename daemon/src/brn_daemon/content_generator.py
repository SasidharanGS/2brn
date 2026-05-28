"""Shared helpers for journal and blog content generation.

Both JournalGenerator and BlogGenerator share identical DB access patterns.
This module provides them as standalone async functions to eliminate duplication.
"""
import logging
from datetime import UTC, datetime

import aiosqlite

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)


async def load_active_instruction_bodies() -> list[str]:
    """Return the body text of all enabled user instructions, ordered by creation."""
    try:
        async with aiosqlite.connect(get_db_path()) as conn:
            cur = await conn.execute(
                "SELECT body FROM user_instructions WHERE enabled = 1 ORDER BY created_at ASC"
            )
            rows = await cur.fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


async def fetch_day_summaries(date_str: str) -> list[str]:
    """Return non-empty activity summaries for the given calendar day (YYYY-MM-DD).

    Uses naive UTC ISO bounds consistent with how started_at is stored.
    """
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT summary FROM activities "
            "WHERE started_at >= ? AND started_at <= ? "
            "AND summary IS NOT NULL AND summary != '' "
            "ORDER BY started_at",
            (f"{date_str}T00:00:00", f"{date_str}T23:59:59.999999"),
        )
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def upsert_generated_content(
    table: str,
    date_str: str,
    content: str,
) -> None:
    """Insert or update generated content for a date, respecting user edits.

    Works for both 'journals' and 'blog_posts' tables — both have identical
    column layouts: (date TEXT UNIQUE, content TEXT, generated_at TEXT,
    edited_by_user INTEGER).
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            f"""INSERT INTO {table} (date, content, generated_at, edited_by_user)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(date) DO UPDATE SET
                  content = excluded.content,
                  generated_at = excluded.generated_at
                WHERE edited_by_user = 0""",
            (date_str, content, now),
        )
        await conn.commit()
