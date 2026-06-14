import asyncio
import json
import logging
import os as _os
import secrets
import time
from contextlib import asynccontextmanager
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
)
from brn_daemon.capture_pipeline import CaptureRecorder, save_screenshot_off_loop
from brn_daemon.capture_policy import CapturePolicy, Frame
from brn_daemon.chat import ChatService
from brn_daemon.config import (
    BlogScheduleConfig,
    ScheduleConfig,
    blog_cron_kwargs,
    get_screenshot_password,
    load_config,
)
from brn_daemon.context import AppContext
from brn_daemon.db import get_conn, get_db_path, init_db
from brn_daemon.dedup import compute_phash
from brn_daemon.embeddings import ChromaStore, EmbeddingService
from brn_daemon.encryption import load_encryption_state, verify_password
from brn_daemon.inference import InferenceQueue
from brn_daemon.journal import JournalGenerator
from brn_daemon.llm import make_chat_fn
from brn_daemon.plugins import EventBus, EventNames, PluginOrchestrator
from brn_daemon.providers import make_embed_client
from brn_daemon.purge import purge_old_captures, sweep_orphaned_screenshots
from brn_daemon.repository import device_id_for_token, touch_device


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx: AppContext = app.state.context
    await init_db()

    # Migrate plugin secrets from legacy "2brn" keychain service to "2brn-plugins"
    from brn_daemon.config import migrate_plugin_keychain_entries as _migrate_keychain
    async with get_conn() as _mig_conn:
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
    ctx.paused = cfg.paused
    ctx.screenshot_key = _load_screenshot_key()
    ctx.api_token = load_or_create_token()
    if ctx.api_token:
        logger.info("Local API authentication: enabled")
    else:
        logger.warning("Local API authentication: DISABLED (could not create token file)")

    chat_fn, stream_fn = make_chat_fn()
    embed_client = make_embed_client()
    ctx.embed_client = embed_client
    chroma = ChromaStore()
    embedding_service = EmbeddingService(embed_client=embed_client, chroma_store=chroma)
    ctx.chroma_store = chroma

    event_bus = EventBus()
    ctx.event_bus = event_bus

    inference_queue = InferenceQueue(
        chat_fn=chat_fn,
        db_path_fn=get_db_path,
        embedding_service=embedding_service,
        event_bus=event_bus,
    )
    ctx.inference_queue = inference_queue
    journal_gen = JournalGenerator(chat_fn=chat_fn)
    blog_gen = BlogGenerator(chat_fn=chat_fn)
    ctx.blog_generator = blog_gen
    chat_service = ChatService(chat_fn=chat_fn, stream_fn=stream_fn, embed_client=embed_client, chroma_store=chroma)
    ctx.journal_generator = journal_gen
    ctx.chat_service = chat_service

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
        **blog_cron_kwargs(cfg.blog_schedule),
        id="blog_job",
        args=[blog_gen, event_bus],
    )
    scheduler.add_job(
        _purge_job,
        "cron", hour=2, minute=0, id="purge_daily",
        args=[ctx],
    )
    scheduler.add_job(
        _reset_capture_count_job,
        "cron", hour=0, minute=0, id="reset_capture_count",
        args=[ctx],
    )
    scheduler.start()
    ctx.scheduler = scheduler

    orchestrator = PluginOrchestrator(event_bus=event_bus, scheduler=scheduler, chat_fn=chat_fn)
    await orchestrator.start()
    ctx.plugin_orchestrator = orchestrator

    asyncio.create_task(_startup_backfill_journal(journal_gen, event_bus, cfg.journal_schedule))
    asyncio.create_task(_startup_backfill_blog(blog_gen, event_bus, cfg.blog_schedule))

    inference_task = asyncio.create_task(inference_queue.run())
    asyncio.create_task(inference_queue.heal_unembedded())
    asyncio.create_task(inference_queue.backfill_unclassified())
    capture_task = asyncio.create_task(_capture_loop(ctx, cfg, inference_queue))

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
            ctx.vault_watcher = vault_watcher
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
    async with get_conn() as conn:
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
    async with get_conn() as conn:
        cur = await conn.execute("SELECT id FROM blog_posts WHERE date = ?", (today.isoformat(),))
        if await cur.fetchone():
            return
    logger.info("Startup backfill: blog missed for %s — running now", today)
    await _blog_job(blog_gen, event_bus, target_date=today)


async def _purge_job(ctx: AppContext) -> None:
    cfg = load_config()
    await purge_old_captures(
        months=cfg.purge_months,
        chroma_store=ctx.chroma_store,
    )
    try:
        await sweep_orphaned_screenshots()
    except Exception:
        logger.exception("Orphan screenshot sweep failed")


async def _reset_capture_count_job(ctx: AppContext) -> None:
    ctx.capture_count_today = 0


async def _start_vault_watcher(vault_watcher, loop) -> None:
    """Bulk-embed existing vault files, then start the file watcher."""
    try:
        await vault_watcher.bulk_embed_all()
    except Exception:
        logger.exception("Vault bulk embed failed")
    vault_watcher.start(loop)


async def _capture_loop(ctx: AppContext, cfg, inference_queue: InferenceQueue):
    policy = CapturePolicy(
        heartbeat_seconds=cfg.capture_interval_seconds,
        similarity_threshold=cfg.similarity_threshold,
        change_cooldown_seconds=cfg.change_cooldown_seconds,
        max_idle_tick_seconds=cfg.max_idle_tick_seconds,
    )
    recorder = CaptureRecorder()
    excluded_apps: set[str] = set()
    exclusion_cache_time = 0.0
    EXCLUSION_CACHE_TTL = 30.0

    while True:
        try:
            await asyncio.sleep(policy.next_tick_seconds(asyncio.get_running_loop().time()))
            now = asyncio.get_running_loop().time()

            if ctx.paused:
                continue

            # Refresh exclusions from DB every 30s instead of every tick
            if (now - exclusion_cache_time) >= EXCLUSION_CACHE_TTL or ctx.exclusions_dirty:
                async with get_conn() as conn:
                    cur = await conn.execute("SELECT app_name FROM app_exclusions")
                    excluded_apps = {row[0] for row in await cur.fetchall()}
                exclusion_cache_time = now
                ctx.exclusions_dirty = False

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
                save_screenshot_off_loop(
                    loop, item.frame.image,
                    key=ctx.screenshot_key,
                    monitor_index=item.frame.monitor_index,
                )
                for item in kept
            ])

            # ── Phase 2: OCR — reused for unchanged heartbeats, else off-loop ─
            ocr_results = await recorder.ocr_kept_frames(loop, kept)

            # ── Phase 3: DB insert + classification routing per kept frame ────
            async with get_conn() as conn:
                for item, file_path, (ocr_text, reused) in zip(kept, file_paths, ocr_results):
                    await recorder.record(
                        conn, inference_queue, item, file_path, ocr_text, reused,
                    )

            ctx.last_captured_at = datetime.now(UTC).isoformat()
            ctx.capture_count_today += 1

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Capture loop error")


async def _touch_device_throttled(ctx, device_id: int) -> None:
    """Refresh a device's ``last_seen_at`` at most once a minute (best-effort)."""
    now = time.monotonic()
    if now - ctx.device_seen.get(device_id, 0.0) < 60:
        return
    ctx.device_seen[device_id] = now
    try:
        await touch_device(device_id)
    except Exception:
        logger.debug("Could not update last_seen_at for device %s", device_id, exc_info=True)


async def _require_api_token(request: Request, call_next):
    """Authenticate every non-public request.

    The *master* token (``~/.2brn/api_token``, shared with the desktop UI) is
    accepted **only on loopback** — the desktop talks only to 127.0.0.1, so the
    master key never needs to be valid over the LAN. LAN callers (paired phones)
    must present a *device* token, which is independently revocable. Device-
    management endpoints (``/devices*``) require the master token on loopback, so
    a phone can't enumerate or revoke devices.

    Inert until a token is loaded into the app context, so the test harness
    (which doesn't run the lifespan) is unaffected. The liveness probe and CORS
    preflight pass through unauthenticated.
    """
    ctx = request.app.state.context
    expected = ctx.api_token
    path = request.url.path
    if not expected or request.method == "OPTIONS" or path in PUBLIC_PATHS:
        return await call_next(request)

    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header[:7].lower() == "bearer " else ""
    client = request.client
    is_loopback = client is not None and client.host in ("127.0.0.1", "::1")

    is_master = bool(token) and is_loopback and secrets.compare_digest(token, expected)
    authorized = is_master
    if not authorized and token:
        device_id = await device_id_for_token(token)
        if device_id is not None:
            authorized = True
            await _touch_device_throttled(ctx, device_id)

    if not authorized:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    # Device management is desktop-only: loopback + the master token.
    if (path == "/devices" or path.startswith("/devices/")) and not is_master:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    return await call_next(request)


def create_app() -> FastAPI:
    from brn_daemon.routes import (
        activities,
        blog_routes,
        captures,
        chat_routes,
        connection_info,
        debug_routes,
        devices,
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
    # The per-app context holds every long-lived service and mutable runtime
    # field (replacing the former global ``app_state`` dict). It exists from app
    # construction so the test harness — which doesn't run the lifespan — has a
    # populated-on-demand context; lifespan fills in the service singletons.
    app.state.context = AppContext()
    # Loopback bearer-token auth (inner). Added before CORS so CORS stays the
    # outermost layer — it answers preflight and decorates the 401 so the UI can
    # read it. Enforced only once a token is loaded into the context (lifespan).
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
    app.include_router(devices.router)
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
