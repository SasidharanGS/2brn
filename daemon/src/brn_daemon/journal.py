import logging
from datetime import date

from brn_daemon.content_generator import (
    fetch_day_summaries,
    load_active_instruction_bodies,
    upsert_generated_content,
)
from brn_daemon.db import get_conn

logger = logging.getLogger(__name__)

JOURNAL_SYSTEM_PROMPT = """You write personal daily journal entries.
Tone: reflective, honest, human, first-person.
Include: what was worked on, key moments, productivity patterns.
Do not be preachy or give unsolicited advice.
Write 2-4 paragraphs in flowing prose. Use markdown."""


def build_journal_prompt(target_date: str, summaries: list[str]) -> str:
    from datetime import date as _date
    parsed = _date.fromisoformat(target_date)
    date_line = f"Date: {target_date} ({parsed.strftime('%A')})"
    if not summaries:
        return (
            f"{date_line}\n"
            "There were no recorded activities for this period. "
            "Write a brief journal entry noting that this was an unrecorded period."
        )
    joined = "\n".join(f"- {s}" for s in summaries)
    return f"{date_line}\n\nActivities:\n{joined}\n\nWrite the journal entry."


def _build_journal_system_prompt(active_instructions: list[str]) -> str:
    if not active_instructions:
        return JOURNAL_SYSTEM_PROMPT
    hints = "\n".join(f"- {inst}" for inst in active_instructions)
    return JOURNAL_SYSTEM_PROMPT + f"\n\nUser-defined rules (follow these):\n{hints}"


class JournalGenerator:
    def __init__(self, chat_fn):
        self._chat_fn = chat_fn

    def set_chat_fn(self, chat_fn) -> None:
        self._chat_fn = chat_fn

    async def generate(self, target_date: date) -> str | None:
        """Generate a full-day journal for target_date. Returns content or None if skipped."""
        date_str = target_date.isoformat()

        async with get_conn() as conn:
            cur = await conn.execute(
                "SELECT id, edited_by_user FROM journals WHERE date = ?", (date_str,)
            )
            existing = await cur.fetchone()
            if existing and existing[1] == 1:
                logger.info("Journal for %s was edited by user — skipping", date_str)
                return None

        summaries = await fetch_day_summaries(date_str)
        active_instructions = await load_active_instruction_bodies()
        system_prompt = _build_journal_system_prompt(active_instructions)
        prompt = build_journal_prompt(date_str, summaries)

        content = await self._chat_fn([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ])

        await upsert_generated_content("journals", date_str, content)
        return content
