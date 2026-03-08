import asyncio
import aiosqlite
import logging
from contextlib import asynccontextmanager
from datetime import date as dt_date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # daemon/.env

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from brn_daemon.db import init_db, get_db_path
from brn_daemon.config import load_config
from brn_daemon.llm import make_chat_fn
from brn_daemon.providers import make_embed_client
from brn_daemon.capture import capture_all_monitors_with_rects, get_active_app, get_app_for_monitor, get_windows_snapshot, save_screenshot
from brn_daemon.dedup import compute_phash, is_duplicate
from brn_daemon.ocr import extract_text, is_text_sparse
from brn_daemon.inference import InferenceQueue
from brn_daemon.embeddings import ChromaStore, EmbeddingService
from brn_daemon.journal import JournalGenerator, JournalMirror, ResumeUpdater
from brn_daemon.blog import BlogGenerator, BlogMirror
from brn_daemon.chat import ChatService
from brn_daemon.purge import purge_old_captures
from brn_daemon.joplin_watcher import JoplinWatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Wire log buffer into root logger so all modules' logs are captured
from brn_daemon.log_buffer import log_buffer as _log_buffer, LogBufferHandler as _LogBufferHandler
logging.getLogger().addHandler(_LogBufferHandler(_log_buffer))

from typing import TypedDict


class AppState(TypedDict, total=False):
    paused: bool
    capture_count_today: int
    last_captured_at: str | None
    journal_generator: JournalGenerator | None
    chat_service: ChatService | None
    vault_watcher: JoplinWatcher | None
    journal_generating: set[str]
    blog_generator: BlogGenerator | None
    blog_generating: set[str]
    chroma_store: ChromaStore | None
    exclusions_dirty: bool


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
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    cfg = load_config()
    app_state["paused"] = cfg.paused

    chat_fn, stream_fn = make_chat_fn()
    embed_client = make_embed_client()
    chroma = ChromaStore()
    embedding_service = EmbeddingService(embed_client=embed_client, chroma_store=chroma)
    app_state["chroma_store"] = chroma
    inference_queue = InferenceQueue(chat_fn=chat_fn, db_path_fn=get_db_path,
                                     embedding_service=embedding_service)
    journal_gen = JournalGenerator(chat_fn=chat_fn)
    journal_mirror = JournalMirror(token=cfg.joplin_token)
    blog_gen = BlogGenerator(chat_fn=chat_fn)
    blog_mirror = BlogMirror(token=cfg.joplin_token)
    app_state["blog_generator"] = blog_gen
    resume_updater = ResumeUpdater(chat_fn=chat_fn, token=cfg.joplin_token)
    chat_service = ChatService(chat_fn=chat_fn, stream_fn=stream_fn, embed_client=embed_client, chroma_store=chroma)

    # VaultWatcher: bulk-embed existing notes, then watch for changes
    vault_watcher = JoplinWatcher(
        embed_client=embed_client,
        chroma_client=chroma.chroma_client,
    )
    app_state["vault_watcher"] = vault_watcher

    app_state["journal_generator"] = journal_gen
    app_state["chat_service"] = chat_service

    scheduler = AsyncIOScheduler(job_defaults={
        "misfire_grace_time": 3600,
        "coalesce": True,
    })
    scheduler.add_job(
        _nightly_pipeline_job,
        "cron", hour=21, minute=0, id="nightly_pipeline",
        args=[journal_gen, journal_mirror, resume_updater, blog_gen, blog_mirror],
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

    asyncio.create_task(_startup_backfill(
        journal_gen, journal_mirror, resume_updater, blog_gen, blog_mirror
    ))

    inference_task = asyncio.create_task(inference_queue.run())
    capture_task = asyncio.create_task(_capture_loop(cfg, inference_queue))

    # Start vault watcher in background (bulk embed on startup, then watch)
    loop = asyncio.get_running_loop()
    asyncio.create_task(_start_vault_watcher(vault_watcher, loop))

    yield

    capture_task.cancel()
    inference_task.cancel()
    vault_watcher.stop()
    scheduler.shutdown()
    await embed_client.aclose()


async def _nightly_pipeline(
    journal_gen: JournalGenerator,
    journal_mirror: JournalMirror,
    resume_updater: ResumeUpdater,
    blog_gen: BlogGenerator,
    blog_mirror: BlogMirror,
    cfg,
    target_date: dt_date,
) -> None:
    try:
        loop = asyncio.get_running_loop()

        journal_content = await journal_gen.generate(target_date=target_date)
        if journal_content:
            await loop.run_in_executor(None, journal_mirror.write_daily_note, target_date, journal_content)

        if journal_content:
            await resume_updater.update_from_journal(journal_content, target_date)

        blog_content = await blog_gen.generate(target_date=target_date)
        if blog_content and cfg.blog_mirror_enabled:
            await loop.run_in_executor(None, blog_mirror.mirror, target_date, blog_content)
    except Exception:
        logger.exception("Nightly pipeline failed for %s", target_date)
        raise


async def _nightly_pipeline_job(
    journal_gen: JournalGenerator,
    journal_mirror: JournalMirror,
    resume_updater: ResumeUpdater,
    blog_gen: BlogGenerator,
    blog_mirror: BlogMirror,
) -> None:
    cfg = load_config()
    await _nightly_pipeline(
        journal_gen, journal_mirror, resume_updater, blog_gen, blog_mirror, cfg, dt_date.today()
    )


async def _purge_job() -> None:
    cfg = load_config()
    await purge_old_captures(months=cfg.purge_months)


async def _reset_capture_count_job() -> None:
    app_state["capture_count_today"] = 0


async def _startup_backfill(
    journal_gen: JournalGenerator,
    journal_mirror: JournalMirror,
    resume_updater: ResumeUpdater,
    blog_gen: BlogGenerator,
    blog_mirror: BlogMirror,
) -> None:
    if datetime.now().hour < 21:
        return
    today = dt_date.today()
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT id FROM journals WHERE date = ?", (today.isoformat(),))
        if await cur.fetchone():
            return
    logger.info("Startup backfill: nightly pipeline missed for %s — running now", today)
    cfg = load_config()
    await _nightly_pipeline(
        journal_gen, journal_mirror, resume_updater, blog_gen, blog_mirror, cfg, today
    )


async def _start_vault_watcher(vault_watcher: JoplinWatcher, loop) -> None:
    """Bulk-embed existing vault files, then start the file watcher."""
    try:
        await vault_watcher.bulk_embed_all()
    except Exception as exc:
        logger.error("Vault bulk embed failed: %s", exc)
    vault_watcher.start(loop)


async def _capture_loop(cfg, inference_queue: InferenceQueue):
    prev_phashes: dict[int, str] = {}  # monitor_index → last phash
    last_heartbeat = 0.0
    excluded_apps: set[str] = set()
    exclusion_cache_time = 0.0
    EXCLUSION_CACHE_TTL = 30.0

    while True:
        try:
            await asyncio.sleep(1)
            now = asyncio.get_running_loop().time()

            if app_state["paused"]:
                continue

            # Refresh exclusions from DB every 30s instead of every tick
            if (now - exclusion_cache_time) >= EXCLUSION_CACHE_TTL or app_state.get("exclusions_dirty"):
                async with aiosqlite.connect(get_db_path()) as conn:
                    cur = await conn.execute("SELECT app_name FROM app_exclusions")
                    excluded_apps = {row[0] for row in await cur.fetchall()}
                exclusion_cache_time = now
                app_state["exclusions_dirty"] = False

            windows = get_windows_snapshot()
            is_heartbeat = (now - last_heartbeat) >= cfg.capture_interval_seconds
            monitors = capture_all_monitors_with_rects()

            # ── Phase 1: dedup + screenshot save (fast, sync) ─────────────────
            # Collect monitors that pass the dedup check so we can fan out OCR
            # in parallel in Phase 2 instead of running it sequentially per monitor.
            pending: list[tuple[int, object, dict, str, str, str, object]] = []
            # pending items: (monitor_idx, img, monitor_rect, app_name, window_title, trigger, file_path)
            for monitor_idx, img, monitor_rect in monitors:
                app_name, window_title = get_app_for_monitor(monitor_rect, windows)

                if app_name in excluded_apps:
                    continue
                current_phash = compute_phash(img)
                prev_phash = prev_phashes.get(monitor_idx)

                is_change = not is_duplicate(current_phash, prev_phash, threshold=0.95)

                if not is_heartbeat and not is_change:
                    continue

                trigger = "heartbeat" if is_heartbeat else "change"
                file_path = save_screenshot(img)
                prev_phashes[monitor_idx] = current_phash
                pending.append((monitor_idx, img, monitor_rect, app_name, window_title, trigger, file_path, current_phash))

            if not pending:
                if is_heartbeat:
                    last_heartbeat = now
                continue

            # ── Phase 2: OCR — run all monitors concurrently in thread pool ───
            loop = asyncio.get_running_loop()
            ocr_tasks = [
                loop.run_in_executor(None, extract_text, item[1])
                for item in pending
            ]
            ocr_results = await asyncio.gather(*ocr_tasks)

            # ── Phase 3: DB inserts + inference enqueue ────────────────────────
            async with aiosqlite.connect(get_db_path()) as conn:
                for item, ocr_text in zip(pending, ocr_results):
                    monitor_idx, img, monitor_rect, app_name, window_title, trigger, file_path, current_phash = item
                    now_iso = datetime.now(timezone.utc).isoformat()
                    cur = await conn.execute(
                        "INSERT INTO captures (captured_at, app_name, window_title, file_path, "
                        "ocr_text, phash, trigger, monitor_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (now_iso, app_name, window_title, str(file_path),
                         ocr_text, current_phash, trigger, monitor_idx)
                    )
                    await conn.commit()
                    capture_id = cur.lastrowid

                    if not is_text_sparse(ocr_text):
                        await inference_queue.enqueue(capture_id, app_name, window_title, ocr_text)

            app_state["last_captured_at"] = datetime.now(timezone.utc).isoformat()
            app_state["capture_count_today"] = app_state.get("capture_count_today", 0) + 1

            if is_heartbeat:
                last_heartbeat = now

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Capture loop error: %s", exc)


def create_app() -> FastAPI:
    from brn_daemon.routes import status, captures, activities
    from brn_daemon.routes import journal_routes, chat_routes, settings_routes, insights_routes
    from brn_daemon.routes import debug_routes
    from brn_daemon.routes import blog_routes
    from brn_daemon.routes import instructions_routes

    app = FastAPI(title="2brn Daemon", lifespan=lifespan)
    # Allow requests from Vite dev server and Electron renderer
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"(file://.*|.*localhost.*)",
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
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("brn_daemon.main:app", host="127.0.0.1", port=7842, reload=False)
