import asyncio
import json
import logging
import os as _os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as dt_date
from pathlib import Path

import aiosqlite
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # daemon/.env

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from brn_daemon.auth import PUBLIC_PATHS, load_or_create_token
from brn_daemon.blog import BlogGenerator
from brn_daemon.capture import (
    capture_all_monitors_with_rects,
    get_app_for_monitor,
    get_windows_snapshot,
    save_screenshot,
)
from brn_daemon.capture_policy import CapturePolicy, Frame, KeptFrame
from brn_daemon.chat import ChatService
from brn_daemon.config import (
    BlogScheduleConfig,
    ScheduleConfig,
    get_screenshot_password,
    load_config,
)
from brn_daemon.db import get_conn, get_db_path, init_db
from brn_daemon.dedup import compute_phash
from brn_daemon.embeddings import ChromaStore, EmbeddingService
from brn_daemon.encryption import load_encryption_state, verify_password
from brn_daemon.inference import InferenceQueue, clone_activity
from brn_daemon.journal import JournalGenerator
from brn_daemon.llm import make_chat_fn
from brn_daemon.ocr import extract_text, is_text_sparse
from brn_daemon.plugins import EventBus, EventNames, PluginOrchestrator
from brn_daemon.providers import make_embed_client
from brn_daemon.purge import purge_old_captures, sweep_orphaned_screenshots
from brn_daemon.timeutil import utc_now_iso


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    if _os.environ.get("BRN_LOG_JSON") == "1":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        ))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


_configure_logging()
logger = logging.getLogger(__name__)

# Wire log buffer into root logger so all modules' logs are captured
from brn_daemon.log_buffer import LogBufferHandler as _LogBufferHandler
from brn_daemon.log_buffer import log_buffer as _log_buffer

_root_logger = logging.getLogger()
if not any(isinstance(h, _LogBufferHandler) for h in _root_logger.handlers):
    _root_logger.addHandler(_LogBufferHandler(_log_buffer))

from typing import TypedDict


class AppState(TypedDict, total=False):
    paused: bool
    capture_count_today: int
    last_captured_at: str | None
    journal_generator: JournalGenerator | None
    chat_service: ChatService | None
    vault_watcher: object | None  # JoplinWatcher when joplin_enabled, else None
    journal_generating: set[str]
    blog_generator: BlogGenerator | None
    blog_generating: set[str]
    chroma_store: ChromaStore | None
    exclusions_dirty: bool
    screenshot_key: bytes | None
    event_bus: EventBus | None
    plugin_orchestrator: PluginOrchestrator | None
    scheduler: AsyncIOScheduler | None
    inference_queue: InferenceQueue | None
    _embed_client_ref: object | None
    api_token: str | None


app_state: AppState = {
    "paused": False,
    "capture_count_today": 0,
    "last_captured_at": None,
    "journal_generator": None,
    "chat_service": None,
    "vault_watcher": None,
    "journal_generating": set(),
    "blog_generator": None,
    "blog_generating": set(),
    "chroma_store": None,
    "exclusions_dirty": True,
    "screenshot_key": None,
    "event_bus": None,
    "plugin_orchestrator": None,
    "scheduler": None,
    "inference_queue": None,
    "_embed_client_ref": None,
    "api_token": None,
}


def _load_screenshot_key() -> bytes | None:
    """Derive the screenshot encryption key from the keychain password.

    Returns ``None`` when encryption is disabled (no password set) or when verification fails
    (wrong/corrupted password). A failure is logged but does not crash the daemon — captures
    fall back to plaintext until the user re-sets the password.
    """
    state = load_encryption_state()
    if state is None:
        return None
    password = get_screenshot_password()
    if not password:
        logger.warning("Screenshot encryption is initialised but no password is in keychain — captures will be plaintext")
        return None
    key = verify_password(password, state)
    if key is None:
        logger.error("Screenshot password in keychain does not match stored verifier — captures will be plaintext")
        return None
    logger.info("Screenshot encryption: enabled")
    return key


def _blog_cron_kwargs(s: "BlogScheduleConfig") -> dict:
    """Convert a BlogScheduleConfig to APScheduler cron trigger kwargs."""
    if s.frequency == "monthly":
        return {"day": s.day, "hour": s.hour, "minute": s.minute}
    if s.frequency == "weekly" and s.days_of_week:
        return {"day_of_week": ",".join(s.days_of_week), "hour": s.hour, "minute": s.minute}
    return {"hour": s.hour, "minute": s.minute}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Migrate plugin secrets from legacy "2brn" keychain service to "2brn-plugins"
    from brn_daemon.config import migrate_plugin_keychain_entries as _migrate_keychain
    async with aiosqlite.connect(get_db_path()) as _mig_conn:
        _mig_conn.row_factory = aiosqlite.Row
        _mig_cur = await _mig_conn.execute(
            "SELECT name, env_keys FROM plugins WHERE env_keys != '[]'"
        )
        _plugin_rows = await _mig_cur.fetchall()
    _entries_to_migrate = []
    for _row in _plugin_rows:
        for _key in json.loads(_row["env_keys"] or "[]"):
            _entries_to_migrate.append((_row["name"], _key))
    if _entries_to_migrate:
        _migrate_keychain(_entries_to_migrate)
        logger.info("Migrated %d plugin keychain entries to 2brn-plugins", len(_entries_to_migrate))

    cfg = load_config()
    app_state["paused"] = cfg.paused
    app_state["screenshot_key"] = _load_screenshot_key()
    app_state["api_token"] = load_or_create_token()
    if app_state["api_token"]:
        logger.info("Local API authentication: enabled")
    else:
        logger.warning("Local API authentication: DISABLED (could not create token file)")

    chat_fn, stream_fn = make_chat_fn()
    embed_client = make_embed_client()
    app_state["_embed_client_ref"] = embed_client
    chroma = ChromaStore()
    embedding_service = EmbeddingService(embed_client=embed_client, chroma_store=chroma)
    app_state["chroma_store"] = chroma

    event_bus = EventBus()
    app_state["event_bus"] = event_bus

    inference_queue = InferenceQueue(
        chat_fn=chat_fn,
        db_path_fn=get_db_path,
        embedding_service=embedding_service,
        event_bus=event_bus,
    )
    app_state["inference_queue"] = inference_queue
    journal_gen = JournalGenerator(chat_fn=chat_fn)
    blog_gen = BlogGenerator(chat_fn=chat_fn)
    app_state["blog_generator"] = blog_gen
    chat_service = ChatService(chat_fn=chat_fn, stream_fn=stream_fn, embed_client=embed_client, chroma_store=chroma)
    app_state["journal_generator"] = journal_gen
    app_state["chat_service"] = chat_service

    scheduler = AsyncIOScheduler(job_defaults={
        "misfire_grace_time": 3600,
        "coalesce": True,
    })
    scheduler.add_job(
        _journal_job,
        "cron",
        hour=cfg.journal_schedule.hour,
        minute=cfg.journal_schedule.minute,
        id="journal_job",
        args=[journal_gen, event_bus],
    )
    scheduler.add_job(
        _blog_job,
        "cron",
        **_blog_cron_kwargs(cfg.blog_schedule),
        id="blog_job",
        args=[blog_gen, event_bus],
    )
    scheduler.add_job(
        _purge_job,
        "cron", hour=2, minute=0, id="purge_daily",
    )
    scheduler.add_job(
        _reset_capture_count_job,
        "cron", hour=0, minute=0, id="reset_capture_count",
    )
    scheduler.start()
    app_state["scheduler"] = scheduler

    orchestrator = PluginOrchestrator(event_bus=event_bus, scheduler=scheduler, chat_fn=chat_fn)
    await orchestrator.start()
    app_state["plugin_orchestrator"] = orchestrator

    asyncio.create_task(_startup_backfill_journal(journal_gen, event_bus, cfg.journal_schedule))
    asyncio.create_task(_startup_backfill_blog(blog_gen, event_bus, cfg.blog_schedule))

    inference_task = asyncio.create_task(inference_queue.run())
    asyncio.create_task(app_state["inference_queue"].heal_unembedded())
    asyncio.create_task(inference_queue.backfill_unclassified())
    capture_task = asyncio.create_task(_capture_loop(cfg, inference_queue))

    # Optional Joplin note embedding watcher — off by default for OSS users.
    vault_watcher = None
    if cfg.joplin_enabled:
        try:
            from brn_daemon.joplin_watcher import JoplinWatcher
            vault_watcher = JoplinWatcher(
                embed_client=embed_client,
                chroma_client=chroma.chroma_client,
                db_path=Path(cfg.joplin_db_path) if cfg.joplin_db_path else None,
            )
            app_state["vault_watcher"] = vault_watcher
            loop = asyncio.get_running_loop()
            asyncio.create_task(_start_vault_watcher(vault_watcher, loop))
        except Exception:
            logger.exception("Failed to start JoplinWatcher — continuing without it")

    try:
        yield
    finally:
        capture_task.cancel()
        inference_task.cancel()
        if vault_watcher is not None:
            try:
                vault_watcher.stop()
            except Exception:
                logger.exception("Vault watcher stop failed")
        try:
            await orchestrator.stop()
        except Exception:
            logger.exception("Plugin orchestrator stop failed")
        scheduler.shutdown()
        await embed_client.aclose()


async def _journal_job(
    journal_gen: JournalGenerator,
    event_bus,
    target_date: dt_date | None = None,
) -> None:
    if target_date is None:
        target_date = dt_date.today()
    try:
        journal_content = await journal_gen.generate(target_date=target_date)
        if journal_content and event_bus:
            await event_bus.emit(EventNames.JOURNAL_GENERATED, {
                "date": target_date.isoformat(),
                "journal_content": journal_content,
            })
    except Exception:
        logger.exception("Journal job failed for %s", target_date)


async def _blog_job(
    blog_gen: BlogGenerator,
    event_bus,
    target_date: dt_date | None = None,
) -> None:
    if target_date is None:
        target_date = dt_date.today()
    try:
        blog_content = await blog_gen.generate(target_date=target_date)
        if blog_content and event_bus:
            await event_bus.emit(EventNames.BLOG_GENERATED, {
                "date": target_date.isoformat(),
                "blog_content": blog_content,
            })
    except Exception:
        logger.exception("Blog job failed for %s", target_date)


async def _startup_backfill_journal(
    journal_gen: JournalGenerator,
    event_bus,
    schedule: ScheduleConfig,
) -> None:
    # Local clock: APScheduler fires the journal job at the local schedule hour,
    # so the "have we already passed it today?" check must be local too.
    now = datetime.now()
    if now.hour < schedule.hour or (now.hour == schedule.hour and now.minute < schedule.minute):
        return
    today = dt_date.today()
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT id FROM journals WHERE date = ?", (today.isoformat(),))
        if await cur.fetchone():
            return
    logger.info("Startup backfill: journal missed for %s — running now", today)
    await _journal_job(journal_gen, event_bus, target_date=today)


async def _startup_backfill_blog(
    blog_gen: BlogGenerator,
    event_bus,
    schedule: "BlogScheduleConfig",
) -> None:
    # Local clock — see _startup_backfill_journal.
    now = datetime.now()
    if schedule.frequency == "monthly" and now.day != schedule.day:
        return
    if schedule.frequency == "weekly" and schedule.days_of_week:
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if day_names[now.weekday()] not in schedule.days_of_week:
            return
    if now.hour < schedule.hour or (now.hour == schedule.hour and now.minute < schedule.minute):
        return
    today = dt_date.today()
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT id FROM blog_posts WHERE date = ?", (today.isoformat(),))
        if await cur.fetchone():
            return
    logger.info("Startup backfill: blog missed for %s — running now", today)
    await _blog_job(blog_gen, event_bus, target_date=today)


async def _purge_job() -> None:
    cfg = load_config()
    await purge_old_captures(
        months=cfg.purge_months,
        chroma_store=app_state.get("chroma_store"),
    )
    try:
        await sweep_orphaned_screenshots()
    except Exception:
        logger.exception("Orphan screenshot sweep failed")


async def _reset_capture_count_job() -> None:
    app_state["capture_count_today"] = 0


async def _start_vault_watcher(vault_watcher, loop) -> None:
    """Bulk-embed existing vault files, then start the file watcher."""
    try:
        await vault_watcher.bulk_embed_all()
    except Exception:
        logger.exception("Vault bulk embed failed")
    vault_watcher.start(loop)


def _save_screenshot_off_loop(
    loop: asyncio.AbstractEventLoop,
    img,
    *,
    key: bytes | None,
    monitor_index: int = 0,
):
    """Schedule save_screenshot (JPEG encode + optional AES + disk write) in the executor."""
    def save_screenshot_bound():
        return save_screenshot(img, key=key, monitor_index=monitor_index)
    save_screenshot_bound.__name__ = "save_screenshot"
    return loop.run_in_executor(None, save_screenshot_bound)


@dataclass(frozen=True)
class _MonitorMemo:
    """The last freshly-OCR'd capture per monitor — what unchanged heartbeats reuse."""

    capture_id: int
    ocr_text: str


async def _ocr_kept_frames(
    loop: asyncio.AbstractEventLoop,
    kept: list[KeptFrame],
    memos: dict[int, _MonitorMemo],
) -> list[tuple[str, bool]]:
    """OCR the kept frames, reusing memoised text for unchanged heartbeat frames.

    Returns one ``(ocr_text, reused)`` pair per frame, in order. An unchanged
    frame is pixel-similar to the monitor's previous kept frame, so rerunning
    tesseract could only re-derive the text we already have.
    """
    def reusable(item: KeptFrame) -> bool:
        return item.unchanged and item.frame.monitor_index in memos

    fresh = [(i, item) for i, item in enumerate(kept) if not reusable(item)]
    fresh_texts = await asyncio.gather(*[
        loop.run_in_executor(None, extract_text, item.frame.image) for _, item in fresh
    ])
    texts: dict[int, str] = {i: text for (i, _), text in zip(fresh, fresh_texts)}
    return [
        (texts[i], False) if i in texts else (memos[item.frame.monitor_index].ocr_text, True)
        for i, item in enumerate(kept)
    ]


async def _capture_loop(cfg, inference_queue: InferenceQueue):
    policy = CapturePolicy(heartbeat_seconds=cfg.capture_interval_seconds)
    ocr_memos: dict[int, _MonitorMemo] = {}
    excluded_apps: set[str] = set()
    exclusion_cache_time = 0.0
    EXCLUSION_CACHE_TTL = 30.0

    while True:
        try:
            await asyncio.sleep(policy.next_tick_seconds(asyncio.get_running_loop().time()))
            now = asyncio.get_running_loop().time()

            if app_state["paused"]:  # type: ignore[typeddict-item]
                continue

            # Refresh exclusions from DB every 30s instead of every tick
            if (now - exclusion_cache_time) >= EXCLUSION_CACHE_TTL or app_state.get("exclusions_dirty"):
                async with aiosqlite.connect(get_db_path()) as conn:
                    cur = await conn.execute("SELECT app_name FROM app_exclusions")
                    excluded_apps = {row[0] for row in await cur.fetchall()}
                exclusion_cache_time = now
                app_state["exclusions_dirty"] = False

            windows = get_windows_snapshot()
            monitors = capture_all_monitors_with_rects()

            loop = asyncio.get_running_loop()

            # ── Phase 1: app detection + phash (CPU-bound, off-loop) ──────────
            app_results = await asyncio.gather(*[
                loop.run_in_executor(None, get_app_for_monitor, monitor_rect, windows)
                for _, _, monitor_rect in monitors
            ])
            frames = [
                Frame(monitor_index=monitor_idx, image=img, monitor_rect=monitor_rect,
                      app_name=app_name, window_title=window_title)
                for (monitor_idx, img, monitor_rect), (app_name, window_title)
                in zip(monitors, app_results)
                if app_name not in excluded_apps
            ]

            # Hash every frame (needed for change detection), but decide what to
            # keep BEFORE writing anything to disk — saving first orphaned a
            # uniquely-named file on every skipped tick, which purge (driven by
            # DB rows) could never reclaim.
            phashes = await asyncio.gather(*[
                loop.run_in_executor(None, compute_phash, frame.image)
                for frame in frames
            ])

            kept = policy.select(frames, phashes, now)
            if not kept:
                continue

            # ── Phase 1b: screenshot save — only for frames we keep ───────────
            file_paths = await asyncio.gather(*[
                _save_screenshot_off_loop(
                    loop, item.frame.image,
                    key=app_state.get("screenshot_key"),
                    monitor_index=item.frame.monitor_index,
                )
                for item in kept
            ])

            # ── Phase 2: OCR — reused for unchanged heartbeats, else off-loop ─
            ocr_results = await _ocr_kept_frames(loop, kept, ocr_memos)

            # ── Phase 3: DB inserts + inference enqueue ────────────────────────
            async with get_conn() as conn:
                for item, file_path, (ocr_text, reused) in zip(kept, file_paths, ocr_results):
                    frame = item.frame
                    now_iso = utc_now_iso()
                    cur = await conn.execute(
                        "INSERT INTO captures (captured_at, app_name, window_title, file_path, "
                        "ocr_text, phash, trigger, monitor_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (now_iso, frame.app_name, frame.window_title, str(file_path),
                         ocr_text, item.phash, item.trigger, frame.monitor_index)
                    )
                    await conn.commit()
                    capture_id: int = cur.lastrowid  # type: ignore[assignment]

                    if reused:
                        cloned = await clone_activity(
                            conn,
                            source_capture_id=ocr_memos[frame.monitor_index].capture_id,
                            capture_id=capture_id,
                            started_at=now_iso,
                        )
                        if cloned:
                            logger.info(
                                "Capture #%d → unchanged heartbeat — reused OCR + classification",
                                capture_id,
                            )
                            continue
                        # Source has no activity yet (inference pending, failed, or
                        # sparse) — fall through to the normal path with the reused
                        # text, but keep the memo pointing at the original root so
                        # later heartbeats can still clone its activity once it lands.
                    else:
                        ocr_memos[frame.monitor_index] = _MonitorMemo(
                            capture_id=capture_id, ocr_text=ocr_text
                        )

                    if not is_text_sparse(ocr_text):
                        await inference_queue.enqueue(
                            capture_id, frame.app_name, frame.window_title, ocr_text, now_iso
                        )
                        logger.info("Capture #%d → inference queued", capture_id)
                    else:
                        logger.info("Capture #%d → saved (sparse text, skipping inference)", capture_id)

            app_state["last_captured_at"] = datetime.now(UTC).isoformat()
            app_state["capture_count_today"] = app_state.get("capture_count_today", 0) + 1

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Capture loop error")


async def _rebuild_ai_clients() -> None:
    """Rebuild chat and embed clients from the current config.

    Called after PUT /settings saves provider changes. Replaces in-memory
    clients in every consumer without restarting the daemon.
    """
    old_embed = app_state.get("_embed_client_ref")
    new_chat_fn, new_stream_fn = make_chat_fn()
    new_embed_client = make_embed_client()

    if old_embed is not None:
        try:
            await old_embed.aclose()  # type: ignore[union-attr]
        except Exception:
            logger.exception("Error closing old embed client during rebuild")

    chroma = app_state.get("chroma_store")
    new_embedding_service = EmbeddingService(embed_client=new_embed_client, chroma_store=chroma)
    new_chat_service = ChatService(
        chat_fn=new_chat_fn,
        stream_fn=new_stream_fn,
        embed_client=new_embed_client,
        chroma_store=chroma,
    )

    app_state["chat_service"] = new_chat_service
    app_state["_embed_client_ref"] = new_embed_client

    iq = app_state.get("inference_queue")
    if iq is not None:
        iq.set_chat_fn(new_chat_fn)
        iq.set_embedding_service(new_embedding_service)

    jg = app_state.get("journal_generator")
    if jg is not None:
        jg.set_chat_fn(new_chat_fn)

    bg = app_state.get("blog_generator")
    if bg is not None:
        bg.set_chat_fn(new_chat_fn)

    po = app_state.get("plugin_orchestrator")
    if po is not None:
        po.chat_fn = new_chat_fn

    logger.info("AI clients rebuilt from updated config")


async def _require_api_token(request: Request, call_next):
    """Reject requests lacking the loopback bearer token.

    Inert until a token is loaded into app_state, so the test harness (which
    doesn't run the lifespan) is unaffected. The liveness probe and CORS
    preflight pass through unauthenticated.
    """
    expected = app_state.get("api_token")
    if expected and request.method != "OPTIONS" and request.url.path not in PUBLIC_PATHS:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        if not (token and secrets.compare_digest(token, expected)):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


def create_app() -> FastAPI:
    from brn_daemon.routes import (
        activities,
        blog_routes,
        captures,
        chat_routes,
        connection_info,
        debug_routes,
        ingest,
        insights_routes,
        instructions_routes,
        journal_routes,
        plugins_routes,
        sessions_routes,
        settings_routes,
        status,
    )

    app = FastAPI(title="2brn Daemon", lifespan=lifespan)
    # Loopback bearer-token auth (inner). Added before CORS so CORS stays the
    # outermost layer — it answers preflight and decorates the 401 so the UI can
    # read it. Enforced only once a token is loaded into app_state (lifespan).
    app.add_middleware(BaseHTTPMiddleware, dispatch=_require_api_token)
    # Allow the Vite dev server and the Electron renderer only. The bearer token
    # is the real gate; this drops the previous any-localhost-port allowance
    # that let any local web page reach the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"file://.*",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(status.router)
    app.include_router(captures.router)
    app.include_router(activities.router)
    app.include_router(journal_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(insights_routes.router)
    app.include_router(debug_routes.router)
    app.include_router(blog_routes.router)
    app.include_router(instructions_routes.router)
    app.include_router(plugins_routes.router)
    app.include_router(sessions_routes.router)
    app.include_router(connection_info.router)
    app.include_router(ingest.router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    from brn_daemon.config import load_config

    # Opt-in LAN access for the mobile companion (off by default). The per-machine
    # bearer token gates every non-public endpoint regardless of the bind address.
    cfg = load_config()
    host = "0.0.0.0" if cfg.lan_access else "127.0.0.1"
    if cfg.lan_access:
        logger.info("LAN access enabled — binding 0.0.0.0:7842 (bearer-token gated)")
    uvicorn.run("brn_daemon.main:app", host=host, port=7842, reload=False)
