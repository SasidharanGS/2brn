import asyncio
import logging
import aiosqlite
from datetime import date, datetime, timezone

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

# ── Joplin notebook IDs (hardcoded — stable, no title-lookup fragility) ───────
# Journal notebook (child of Second Brain): daily journal notes live here
JOPLIN_JOURNAL_NOTEBOOK_ID = "6f38474f663240adade6639de762abf7"
# Memories notebook (child of Second Brain): used by ResumeUpdater to find notes
JOPLIN_MEMORIES_NOTEBOOK_ID = "c05faf5d2b9c4b07906365ab201f203e"
# Resume notebook: ResumeUpdater appends activity entries here
JOPLIN_RESUME_NOTEBOOK_ID = "4eb014cd7400401bbe8cdb3c22b48830"

# Resume note titles that ResumeUpdater considers for updates
RESUME_NOTE_TITLES = [
    "Technical Skills",
    "Work Experience",
    "Projects",
    "Achievements & Recognition",
    "Personal Projects",
]

JOURNAL_SYSTEM_PROMPT = """You write personal daily journal entries.
Tone: reflective, honest, human, first-person.
Include: what was worked on, key moments, productivity patterns.
Do not be preachy or give unsolicited advice.
Write 2-4 paragraphs in flowing prose. Use markdown."""

RESUME_UPDATE_SYSTEM_PROMPT = """You are a resume assistant. Given a daily work journal entry,
decide if any of the listed resume notes need a brief update.

Rules:
- Only suggest updates for genuinely noteworthy things: new tech used, project milestones,
  skills demonstrated, recognitions received.
- Routine daily work (bug fixes, meetings, small tasks) does NOT warrant a resume update.
- For each note to update, write a concise single bullet point (max 20 words).
- If nothing is noteworthy enough, output exactly: NONE

Output format (one per line, nothing else):
NOTE_TITLE | bullet text

Example:
Technical Skills | Used DeepEval for LLM conversation simulation testing in AgentHub.
NONE"""


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


def _date_to_note_title(d: date) -> str:
    """Convert a date to DD-MM-YY note title format."""
    return d.strftime("%d-%m-%y")


class JournalGenerator:
    def __init__(self, gateway):
        self._gateway = gateway

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
        content = await self._gateway.chat_complete([
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


class JournalMirror:
    """Mirrors the daily full-day journal to Joplin via the Web Clipper API.

    Writes one note per day titled "DD-MM-YY" into the Journal notebook
    (nested under Second Brain). Falls back silently if Joplin is not running.
    """

    # Notebook ID for Journal (child of Second Brain) — stable, no title-lookup needed
    NOTEBOOK_ID = JOPLIN_JOURNAL_NOTEBOOK_ID

    def __init__(self, token: str = "", port: int = 41184):
        self._token = token
        self._port = port

    def _api(self, method: str, endpoint: str, body: dict | None = None) -> dict | None:
        """Make a synchronous HTTP call to the Joplin Web Clipper API."""
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
            logger.warning("JournalMirror API error: %s", exc)
            return None

    def _find_note(self, title: str) -> str | None:
        """Search for a note by exact title. Returns note ID or None."""
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

    def write_daily_note(self, target_date: date, content: str) -> None:
        """Write the full-day journal to Joplin. Creates note if absent, replaces if exists."""
        note_title = _date_to_note_title(target_date)
        now_str = datetime.now().strftime("%H:%M")

        note_body = (
            f"# Journal — {target_date.isoformat()}\n"
            f"_Generated by 2brn at {now_str}_\n\n"
            f"{content}\n"
        )

        note_id = self._find_note(note_title)

        if note_id:
            # Overwrite existing note (regeneration case)
            self._api("PUT", f"/notes/{note_id}", {"body": note_body})
            logger.info("Updated Joplin journal note '%s'", note_title)
            return

        # Create new note in the Journal notebook
        payload: dict = {
            "title": note_title,
            "body": note_body,
            "parent_id": self.NOTEBOOK_ID,
        }
        result = self._api("POST", "/notes", payload)
        if result:
            logger.info("Created Joplin journal note '%s'", note_title)
        else:
            logger.warning("Could not mirror journal to Joplin (app not running?) — skipping")


class ResumeUpdater:
    """After journal generation, uses the LLM to decide which Resume notes to update.

    Reads the daily journal content, sends it + the list of Resume note titles to the
    LLM, parses the response, and appends AI-suggested bullet points under a
    '## Recent Activity' section in each relevant Resume note via Joplin Web Clipper.
    Falls back silently if the gateway is down or Joplin is not running.
    """

    def __init__(self, gateway, token: str = "", port: int = 41184):
        self._gateway = gateway
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
            logger.warning("ResumeUpdater API error: %s", exc)
            return None

    def _find_resume_note(self, title: str) -> str | None:
        """Search for a Resume note by exact title. Returns note ID or None."""
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

    def _append_to_note(self, note_id: str, bullet: str, today: date) -> None:
        """Append a dated bullet under '## Recent Activity' section in a Resume note."""
        existing = self._api("GET", f"/notes/{note_id}?fields=id,body")
        if not existing:
            return

        body = existing.get("body", "")
        dated_bullet = f"- **{today.isoformat()}**: {bullet}"

        if "## Recent Activity" in body:
            # Append after the section header
            new_body = body.rstrip() + f"\n{dated_bullet}\n"
        else:
            # Add the section at the end
            new_body = body.rstrip() + f"\n\n## Recent Activity\n{dated_bullet}\n"

        self._api("PUT", f"/notes/{note_id}", {"body": new_body})

    async def update_from_journal(self, journal_content: str, target_date: date) -> None:
        """Ask the LLM which Resume notes to update based on today's journal, then patch them."""
        if not journal_content or not journal_content.strip():
            return

        note_list = "\n".join(f"- {t}" for t in RESUME_NOTE_TITLES)
        user_prompt = (
            f"Today's journal entry ({target_date.isoformat()}):\n\n"
            f"{journal_content}\n\n"
            f"Resume notes available to update:\n{note_list}\n\n"
            "Which of these notes (if any) should be updated based on the journal?"
        )

        try:
            response = await self._gateway.chat_complete([
                {"role": "system", "content": RESUME_UPDATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ])
        except Exception as exc:
            logger.warning("ResumeUpdater: gateway call failed — %s", exc)
            return

        if not response or response.strip().upper() == "NONE":
            logger.info("ResumeUpdater: no resume updates needed for %s", target_date.isoformat())
            return

        updates: dict[str, str] = {}
        for line in response.strip().splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            parts = line.split("|", 1)
            if len(parts) != 2:
                continue
            note_title = parts[0].strip()
            bullet = parts[1].strip()
            if note_title in RESUME_NOTE_TITLES and bullet:
                updates[note_title] = bullet

        if not updates:
            logger.info("ResumeUpdater: LLM response parsed — nothing actionable for %s", target_date.isoformat())
            return

        for note_title, bullet in updates.items():
            note_id = await asyncio.get_running_loop().run_in_executor(
                None, self._find_resume_note, note_title
            )
            if note_id:
                await asyncio.get_running_loop().run_in_executor(
                    None, self._append_to_note, note_id, bullet, target_date
                )
                logger.info("ResumeUpdater: appended to '%s'", note_title)
            else:
                logger.warning("ResumeUpdater: could not find Resume note '%s'", note_title)
