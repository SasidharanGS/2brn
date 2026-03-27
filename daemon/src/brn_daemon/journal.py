import logging
import aiosqlite
from datetime import date, datetime, timezone

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

JOURNAL_SYSTEM_PROMPT = """You write personal daily journal entries.
Tone: reflective, honest, human, first-person.
Include: what was worked on, key moments, productivity patterns.
Do not be preachy or give unsolicited advice.
Write 2-4 paragraphs in flowing prose. Use markdown."""


def build_journal_prompt(
    target_date: str,
    summaries: list[str],
) -> str:
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


async def _load_active_instruction_bodies() -> list[str]:
    try:
        async with aiosqlite.connect(get_db_path()) as conn:
            cur = await conn.execute(
                "SELECT body FROM user_instructions WHERE enabled = 1 ORDER BY created_at ASC"
            )
            rows = await cur.fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def _build_journal_system_prompt(active_instructions: list[str]) -> str:
    if not active_instructions:
        return JOURNAL_SYSTEM_PROMPT
    hints = "\n".join(f"- {inst}" for inst in active_instructions)
    return JOURNAL_SYSTEM_PROMPT + f"\n\nUser-defined rules (follow these):\n{hints}"


class JournalGenerator:
    def __init__(self, chat_fn):
        self._chat_fn = chat_fn

    async def generate(self, target_date: date) -> str | None:
        """Generate a full-day journal for target_date. Returns content or None if skipped."""
        date_str = target_date.isoformat()

        async with aiosqlite.connect(get_db_path()) as conn:
            # Skip if user has edited this journal entry
            cur = await conn.execute(
                "SELECT id, edited_by_user FROM journals WHERE date = ?",
                (date_str,),
            )
            existing = await cur.fetchone()
            if existing and existing[1] == 1:
                logger.info("Journal for %s was edited by user — skipping", date_str)
                return None

            # Fetch all activities for the day
            cur = await conn.execute(
                "SELECT summary FROM activities "
                "WHERE started_at >= ? AND started_at <= ? "
                "AND summary IS NOT NULL AND summary != '' "
                "ORDER BY started_at",
                (f"{date_str}T00:00:00", f"{date_str}T23:59:59.999999"),
            )
            rows = await cur.fetchall()
            summaries = [r[0] for r in rows]

        prompt = build_journal_prompt(date_str, summaries)
        active_instructions = await _load_active_instruction_bodies()
        system_prompt = _build_journal_system_prompt(active_instructions)
        content = await self._chat_fn([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ])

        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                    """INSERT INTO journals (date, content, generated_at, edited_by_user)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(date) DO UPDATE SET
                     content = excluded.content,
                     generated_at = excluded.generated_at
                   WHERE edited_by_user = 0""",
                (date_str, content, now),
            )
            await conn.commit()

        return content
