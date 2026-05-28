import logging
from datetime import date

import aiosqlite

from brn_daemon.content_generator import fetch_day_summaries, upsert_generated_content
from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

BLOG_SYSTEM_PROMPT = """You are a technical writer helping a software engineer maintain a public dev log.
Given a day's activities and journal entry — write a concise dev log entry in first person. Focus on: what was learned, what was built, what was tried or experimented with.

Write for a public technical audience. Use a direct, honest, personal tone.
Structure: a short narrative opening, then **What I learned**, **What I built**, **Experimenting with** sections as applicable. Only include sections with content.

IMPORTANT: This is a public blog. Omit anything company-confidential — client names, internal system names, proprietary business logic, employer-specific work tasks, or anything that could identify a client or employer's internal systems. If an activity is purely corporate work with no public learning value, skip it entirely. Personal projects, open-source tools, technical learnings, and experiments are all fair game."""


def build_blog_prompt(
    target_date: str,
    summaries: list[str],
    journal_content: str | None,
) -> str:
    parts = [f"Date: {target_date}"]
    if summaries:
        parts.append("\n## Activities\n" + "\n".join(f"- {s}" for s in summaries))
    else:
        parts.append("\n## Activities\nNo recorded activities for this day.")
    if journal_content:
        parts.append(f"\n## Journal Entry\n{journal_content}")
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
                "SELECT content FROM journals WHERE date = ?", (date_str,)
            )
            journal_row = await cur.fetchone()
            journal_content = journal_row[0] if journal_row else None

        summaries = await fetch_day_summaries(date_str)
        prompt = build_blog_prompt(date_str, summaries, journal_content)

        content = await self._chat_fn([
            {"role": "system", "content": BLOG_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])

        await upsert_generated_content("blog_posts", date_str, content)
        return content
