import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

from brn_daemon.db import get_conn
from brn_daemon.timeutil import utc_iso_to_local_date, utc_now_iso

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"work", "research", "play", "learning", "communication", "creative", "admin", "other"}
VALID_STATES = {"productive", "focused", "chilling", "procrastinating", "distracted", "in-meeting", "idle"}

# Caps the number of pending inference jobs. When the gateway is down for a long
# period the loop keeps capturing — without a cap this queue grows until OOM.
INFERENCE_QUEUE_MAX = 500

# Number of concurrent LLM inference workers. Each worker independently dequeues
# and calls the gateway, so up to this many requests can be in-flight at once.
# At ~3-5s per call, 5 workers sustain ~1 inference/second without queue build-up.
INFERENCE_CONCURRENCY = 5

# Maximum characters of OCR text to include in the inference prompt.
# Longer screenshots are silently truncated to keep token usage predictable.
MAX_OCR_CHARS = 2000

INFERENCE_SYSTEM_PROMPT = """You are analyzing screen activity. Given screen content, return ONLY a valid JSON object with these exact keys:
- summary: string, 1-2 sentences describing what the user was doing
- tags: array of strings, specific activity keywords (max 5)
- task_category: one of exactly: work, research, play, learning, communication, creative, admin, other
- task_category_confidence: float between 0 and 1
- productivity_state: one of exactly: productive, focused, chilling, procrastinating, distracted, in-meeting, idle
- productivity_confidence: float between 0 and 1
- app_name: string or null — ONLY set this when a user-defined rule explicitly says to override the app name (e.g. "classify YouTube as YouTube"). Otherwise always return null.
Return ONLY the JSON. No explanation. No markdown."""


def _build_inference_system_prompt(active_instructions: list[str]) -> str:
    if not active_instructions:
        return INFERENCE_SYSTEM_PROMPT
    hints = "\n".join(f"- {inst}" for inst in active_instructions)
    return INFERENCE_SYSTEM_PROMPT + f"\n\nUser-defined rules (follow these):\n{hints}"


@dataclass
class InferenceResult:
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    task_category: str = "other"
    task_category_confidence: float = 0.0
    productivity_state: str = "idle"
    productivity_confidence: float = 0.0
    app_name_override: str | None = None


def build_inference_prompt(app_name: str, window_title: str, ocr_text: str) -> str:
    return f"App: {app_name} | Window: {window_title}\nOCR text:\n{ocr_text[:MAX_OCR_CHARS]}"


def parse_inference_response(raw: str) -> InferenceResult:
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        category = data.get("task_category", "other")
        if category not in VALID_CATEGORIES:
            category = "other"
        state = data.get("productivity_state", "idle")
        if state not in VALID_STATES:
            state = "idle"
        return InferenceResult(
            summary=str(data.get("summary", "")),
            tags=list(data.get("tags", [])),
            task_category=category,
            task_category_confidence=float(data.get("task_category_confidence", 0.0)),
            productivity_state=state,
            productivity_confidence=float(data.get("productivity_confidence", 0.0)),
            app_name_override=data.get("app_name") or None,
        )
    except Exception:
        logger.warning("Failed to parse inference response | raw: %s", raw[:200])
        # Not logger.exception here — parse failures are expected (malformed LLM output)
        # and the raw snippet is the relevant debug info, not the stack trace.
        return InferenceResult()


class InferenceQueue:
    def __init__(self, chat_fn, db_path_fn, embedding_service=None, event_bus=None):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=INFERENCE_QUEUE_MAX)
        self._chat_fn = chat_fn
        self._db_path_fn = db_path_fn
        self._embedding_service = embedding_service
        self._event_bus = event_bus  # plugins.EventBus or None
        self._instructions_cache: list[str] | None = None
        self._instructions_cache_at: float = 0.0
        self._INSTRUCTIONS_CACHE_TTL = 30.0
        self._failed_captures: set[int] = set()
        self._dropped: int = 0

    async def enqueue(self, capture_id: int, app_name: str, window_title: str, ocr_text: str,
                      captured_at: str | None = None) -> None:
        try:
            self._queue.put_nowait((capture_id, app_name, window_title, ocr_text, captured_at))
        except asyncio.QueueFull:
            self._dropped += 1
            logger.warning(
                "Inference queue full (%d items) — dropping capture %d (%d dropped total). "
                "Gateway may be unreachable.",
                INFERENCE_QUEUE_MAX, capture_id, self._dropped,
            )

    async def _load_instructions(self) -> list[str]:
        """Return active instruction bodies, using a 30-second in-memory cache."""
        import aiosqlite
        loop = asyncio.get_running_loop()
        now = loop.time()
        if (
            self._instructions_cache is not None
            and (now - self._instructions_cache_at) < self._INSTRUCTIONS_CACHE_TTL
        ):
            return self._instructions_cache
        try:
            async with aiosqlite.connect(self._db_path_fn()) as conn:
                cur = await conn.execute(
                    "SELECT body FROM user_instructions WHERE enabled = 1 ORDER BY created_at ASC"
                )
                rows = await cur.fetchall()
            self._instructions_cache = [r[0] for r in rows]
            self._instructions_cache_at = now
        except Exception:
            self._instructions_cache = self._instructions_cache or []
        return self._instructions_cache  # type: ignore[return-value]

    def invalidate_instructions_cache(self) -> None:
        """Force next _load_instructions call to re-query the DB."""
        self._instructions_cache = None
        self._instructions_cache_at = 0.0

    async def _lookup_captured_at(self, capture_id: int) -> str | None:
        """Return the capture's own timestamp, or None if the row is gone."""
        import aiosqlite
        try:
            async with aiosqlite.connect(self._db_path_fn()) as conn:
                cur = await conn.execute(
                    "SELECT captured_at FROM captures WHERE id = ?", (capture_id,)
                )
                row = await cur.fetchone()
            return row[0] if row else None
        except Exception:
            return None

    async def heal_unembedded(self) -> int:
        """Re-embed activities where chroma_id IS NULL. Called at daemon startup."""
        if not self._embedding_service:
            return 0
        import aiosqlite
        healed = 0
        BATCH = 200
        while True:
            async with aiosqlite.connect(self._db_path_fn()) as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(
                    """SELECT a.id, a.summary, a.tags, a.task_category, a.productivity_state,
                              a.started_at, c.app_name
                       FROM activities a
                       LEFT JOIN captures c ON c.id = a.capture_id
                       WHERE a.chroma_id IS NULL AND a.summary IS NOT NULL AND trim(a.summary) != ''
                       LIMIT ?""",
                    (BATCH,),
                )
                rows = list(await cur.fetchall())
            if not rows:
                break
            batch_healed = 0
            for row in rows:
                try:
                    metadata = {
                        "timestamp": row["started_at"] or "",
                        "app_name": row["app_name"] or "",
                        "tags": row["tags"] or "[]",
                        "date": utc_iso_to_local_date(row["started_at"]),
                        "task_category": row["task_category"] or "",
                        "productivity_state": row["productivity_state"] or "",
                        "source": "activity",
                    }
                    await self._embedding_service.embed_activity(
                        activity_id=row["id"],
                        summary=row["summary"],
                        metadata=metadata,
                    )
                    batch_healed += 1
                except Exception:
                    logger.exception("Heal-pass failed for activity #%d", row["id"])
            healed += batch_healed
            # Stop if a whole batch made no progress (e.g. embed provider down) so a
            # persistent failure can't loop forever; otherwise continue until drained.
            if batch_healed == 0 or len(rows) < BATCH:
                break
        if healed:
            logger.info("Heal-pass: re-embedded %d activities with chroma_id IS NULL", healed)
        return healed

    @property
    def failed_capture_ids(self) -> list[int]:
        """Return capture IDs that failed inference (for /debug/status)."""
        return sorted(self._failed_captures)

    @property
    def dropped_count(self) -> int:
        """Captures dropped because the inference queue was full (gateway backlog)."""
        return self._dropped

    async def _process_one(self, capture_id: int, app_name: str, window_title: str, ocr_text: str,
                           captured_at: str | None = None) -> None:
        """Process a single inference item: call LLM, write to SQLite, embed.

        ``started_at`` is the capture's own timestamp (when the screenshot was
        taken), never the inference time — a queue backlog must not re-date
        activities to when they were processed. Falls back to the capture row's
        ``captured_at`` (then to now) when the caller didn't supply it.
        """
        try:
            if captured_at is None:
                captured_at = await self._lookup_captured_at(capture_id)
            started_at = captured_at or utc_now_iso()
            active_instructions = await self._load_instructions()
            system_prompt = _build_inference_system_prompt(active_instructions)
            user_prompt = build_inference_prompt(app_name, window_title, ocr_text)
            raw = await self._chat_fn([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            result = parse_inference_response(raw)
            async with get_conn(self._db_path_fn()) as conn:
                cur = await conn.execute(
                    """INSERT INTO activities
                       (capture_id, started_at, summary, tags, task_category,
                        task_category_confidence, productivity_state, productivity_confidence,
                        app_name_override)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (capture_id, started_at, result.summary, json.dumps(result.tags),
                     result.task_category, result.task_category_confidence,
                     result.productivity_state, result.productivity_confidence,
                     result.app_name_override),
                )
                await conn.commit()
                activity_id = cur.lastrowid

            # Embed into ChromaDB immediately so chat can find it
            if self._embedding_service and result.summary:
                metadata = {
                    "timestamp": started_at,
                    "app_name": app_name or "",
                    "tags": json.dumps(result.tags),
                    "date": utc_iso_to_local_date(started_at),
                    "task_category": result.task_category,
                    "productivity_state": result.productivity_state,
                    "source": "activity",
                }
                try:
                    await self._embedding_service.embed_activity(
                        activity_id=activity_id,
                        summary=result.summary,
                        metadata=metadata,
                    )
                except Exception:
                    logger.exception(
                        "Embedding failed for activity #%d (capture #%d) — chroma_id will remain NULL; heal-pass will retry on next startup",
                        activity_id, capture_id,
                    )
            logger.info("Capture #%d → inference done → activity #%d → embed queued", capture_id, activity_id)

            if self._event_bus is not None:
                # Fire-and-forget: handler exceptions are swallowed inside the bus.
                from brn_daemon.plugins.events import EventNames as _EN
                await self._event_bus.emit(_EN.CAPTURE_INFERRED, {
                    "summary": result.summary,
                    "task_category": result.task_category,
                    "productivity_state": result.productivity_state,
                    "app_name": result.app_name_override or app_name or "",
                    "timestamp": started_at,
                    "tags": result.tags,
                })
        except Exception:
            logger.exception("Inference failed for capture %d", capture_id)
            self._failed_captures.add(capture_id)

    async def _worker(self) -> None:
        """A single concurrent worker: dequeues items and processes them indefinitely."""
        while True:
            capture_id, app_name, window_title, ocr_text, captured_at = await self._queue.get()
            try:
                await self._process_one(capture_id, app_name, window_title, ocr_text, captured_at)
            finally:
                self._queue.task_done()

    async def run(self) -> None:
        """Spawn INFERENCE_CONCURRENCY workers and run them until cancelled."""
        workers = [asyncio.create_task(self._worker()) for _ in range(INFERENCE_CONCURRENCY)]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise
