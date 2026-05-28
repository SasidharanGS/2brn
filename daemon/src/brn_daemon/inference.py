import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

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
    except Exception as exc:
        logger.warning("Failed to parse inference response: %s | raw: %s", exc, raw[:200])
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
    async def enqueue(self, capture_id: int, app_name: str, window_title: str, ocr_text: str) -> None:
        try:
            self._queue.put_nowait((capture_id, app_name, window_title, ocr_text))
        except asyncio.QueueFull:
            logger.warning(
                "Inference queue full (%d items) — dropping capture %d. "
                "Gateway may be unreachable.",
                INFERENCE_QUEUE_MAX, capture_id,
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

    async def _process_one(self, capture_id: int, app_name: str, window_title: str, ocr_text: str) -> None:
        """Process a single inference item: call LLM, write to SQLite, embed."""
        import aiosqlite
        try:
            active_instructions = await self._load_instructions()
            system_prompt = _build_inference_system_prompt(active_instructions)
            user_prompt = build_inference_prompt(app_name, window_title, ocr_text)
            raw = await self._chat_fn([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            result = parse_inference_response(raw)
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")
            async with aiosqlite.connect(self._db_path_fn()) as conn:
                cur = await conn.execute(
                    """INSERT INTO activities
                       (capture_id, started_at, summary, tags, task_category,
                        task_category_confidence, productivity_state, productivity_confidence,
                        app_name_override)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (capture_id, now, result.summary, json.dumps(result.tags),
                     result.task_category, result.task_category_confidence,
                     result.productivity_state, result.productivity_confidence,
                     result.app_name_override),
                )
                await conn.commit()
                activity_id = cur.lastrowid

            # Embed into ChromaDB immediately so chat can find it
            if self._embedding_service and result.summary:
                metadata = {
                    "timestamp": now,
                    "app_name": app_name or "",
                    "tags": json.dumps(result.tags),
                    "date": now[:10],
                    "task_category": result.task_category,
                    "productivity_state": result.productivity_state,
                    "source": "activity",
                }
                await self._embedding_service.embed_activity(
                    activity_id=activity_id,
                    summary=result.summary,
                    metadata=metadata,
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
                    "timestamp": now,
                    "tags": result.tags,
                })
        except Exception as exc:
            logger.error("Inference failed for capture %d: %s", capture_id, exc)

    async def _worker(self) -> None:
        """A single concurrent worker: dequeues items and processes them indefinitely."""
        while True:
            capture_id, app_name, window_title, ocr_text = await self._queue.get()
            try:
                await self._process_one(capture_id, app_name, window_title, ocr_text)
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
