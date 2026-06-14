import asyncio
import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from brn_daemon.config import (
    BlogScheduleConfig,
    ScheduleConfig,
    blog_cron_kwargs,
    delete_screenshot_password,
    get_chat_api_key,
    get_embed_api_key,
    load_config,
    save_config,
    set_chat_api_key,
    set_embed_api_key,
    set_screenshot_password,
)
from brn_daemon.context import AppContext, get_context
from brn_daemon.db import get_conn
from brn_daemon.encryption import (
    decrypt_all_screenshots,
    delete_encryption_state,
    encrypt_existing_screenshots,
    initialize_encryption,
    is_initialised,
    load_encryption_state,
    re_encrypt_all_screenshots,
    verify_password,
)
from brn_daemon.repository import mark_captures_decrypted, mark_captures_encrypted
from brn_daemon.services import rebuild_ai_clients

router = APIRouter()
logger = logging.getLogger(__name__)

# Hold strong references to fire-and-forget background tasks: asyncio keeps only
# weak references, so without this the GC can cancel a long backfill/encrypt job
# mid-run. The done-callback drops the reference (and surfaces any exception).
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class ProviderConfigOut(BaseModel):
    type: str
    base_url: str
    model: str
    extra_headers: dict = {}


class ProviderConfigIn(BaseModel):
    type: str | None = None
    base_url: str | None = None
    model: str | None = None
    extra_headers: dict | None = None
    api_key: str | None = None


class ScheduleConfigIn(BaseModel):
    hour: Annotated[int, Field(ge=0, le=23)]
    minute: Annotated[int, Field(ge=0, le=59)]


class SettingsResponse(BaseModel):
    chat_provider: ProviderConfigOut
    embed_provider: ProviderConfigOut
    has_chat_key: bool
    has_embed_key: bool
    capture_interval_seconds: int
    change_cooldown_seconds: float
    max_idle_tick_seconds: float
    similarity_threshold: float
    purge_months: int
    paused: bool
    lan_access: bool
    screenshot_encryption_enabled: bool
    joplin_enabled: bool
    joplin_db_path: str
    journal_schedule: ScheduleConfigIn
    blog_schedule: dict


class BlogScheduleIn(BaseModel):
    frequency: Annotated[str, Field(pattern=r"^(daily|monthly|weekly)$")]
    hour: Annotated[int, Field(ge=0, le=23)] = 21
    minute: Annotated[int, Field(ge=0, le=59)] = 0
    day: Annotated[int, Field(ge=1, le=28)] = 1
    days_of_week: list[str] = []

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[str]) -> list[str]:
        valid = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        bad = set(v) - valid
        if bad:
            raise ValueError(f"Invalid day(s): {bad}")
        return v


class SettingsUpdateRequest(BaseModel):
    chat_provider: ProviderConfigIn | None = None
    embed_provider: ProviderConfigIn | None = None
    capture_interval_seconds: Annotated[int, Field(ge=1)] | None = None
    change_cooldown_seconds: Annotated[float, Field(ge=0)] | None = None
    max_idle_tick_seconds: Annotated[float, Field(ge=1)] | None = None
    similarity_threshold: Annotated[float, Field(gt=0.5, le=1.0)] | None = None
    purge_months: Annotated[int, Field(ge=1)] | None = None
    lan_access: bool | None = None
    joplin_enabled: bool | None = None
    joplin_db_path: str | None = None
    journal_schedule: ScheduleConfigIn | None = None
    blog_schedule: BlogScheduleIn | None = None


class ExclusionRequest(BaseModel):
    app_name: str


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    cfg = await asyncio.get_event_loop().run_in_executor(None, load_config)
    cp = cfg.chat_provider
    ep = cfg.embed_provider
    return SettingsResponse(
        chat_provider=ProviderConfigOut(type=cp.type, base_url=cp.base_url, model=cp.model, extra_headers=cp.extra_headers),
        embed_provider=ProviderConfigOut(type=ep.type, base_url=ep.base_url, model=ep.model, extra_headers=ep.extra_headers),
        has_chat_key=bool(get_chat_api_key()),
        has_embed_key=bool(get_embed_api_key()),
        capture_interval_seconds=cfg.capture_interval_seconds,
        change_cooldown_seconds=cfg.change_cooldown_seconds,
        max_idle_tick_seconds=cfg.max_idle_tick_seconds,
        similarity_threshold=cfg.similarity_threshold,
        purge_months=cfg.purge_months,
        paused=cfg.paused,
        lan_access=cfg.lan_access,
        screenshot_encryption_enabled=is_initialised(),
        joplin_enabled=cfg.joplin_enabled,
        joplin_db_path=cfg.joplin_db_path,
        journal_schedule=ScheduleConfigIn(hour=cfg.journal_schedule.hour, minute=cfg.journal_schedule.minute),
        blog_schedule={
            "frequency": cfg.blog_schedule.frequency,
            "hour": cfg.blog_schedule.hour,
            "minute": cfg.blog_schedule.minute,
            "day": cfg.blog_schedule.day,
            "days_of_week": cfg.blog_schedule.days_of_week,
        },
    )


@router.put("/settings")
async def update_settings(body: SettingsUpdateRequest, ctx: AppContext = Depends(get_context)):
    cfg = load_config()
    if body.chat_provider:
        p = body.chat_provider
        if p.type is not None:
            cfg.chat_provider.type = p.type
        if p.base_url is not None:
            cfg.chat_provider.base_url = p.base_url
        if p.model is not None:
            cfg.chat_provider.model = p.model
        if p.extra_headers is not None:
            cfg.chat_provider.extra_headers = p.extra_headers
        if p.api_key:
            set_chat_api_key(p.api_key)
    if body.embed_provider:
        p = body.embed_provider
        if p.type is not None:
            cfg.embed_provider.type = p.type
        if p.base_url is not None:
            cfg.embed_provider.base_url = p.base_url
        if p.model is not None:
            cfg.embed_provider.model = p.model
        if p.extra_headers is not None:
            cfg.embed_provider.extra_headers = p.extra_headers
        if p.api_key:
            set_embed_api_key(p.api_key)
    if body.capture_interval_seconds is not None:
        cfg.capture_interval_seconds = body.capture_interval_seconds
    if body.change_cooldown_seconds is not None:
        cfg.change_cooldown_seconds = body.change_cooldown_seconds
    if body.max_idle_tick_seconds is not None:
        cfg.max_idle_tick_seconds = body.max_idle_tick_seconds
    if body.similarity_threshold is not None:
        cfg.similarity_threshold = body.similarity_threshold
    # Cross-field check on the merged result: an idle ceiling at or above the
    # heartbeat would never be reached (sleeps are clamped to the heartbeat),
    # so reject it as almost certainly a mistake.
    if cfg.max_idle_tick_seconds >= cfg.capture_interval_seconds:
        raise HTTPException(
            400,
            f"max_idle_tick_seconds ({cfg.max_idle_tick_seconds}) must be smaller than "
            f"capture_interval_seconds ({cfg.capture_interval_seconds})",
        )
    if body.purge_months is not None:
        cfg.purge_months = body.purge_months
    if body.lan_access is not None:
        cfg.lan_access = body.lan_access
    if body.joplin_enabled is not None:
        cfg.joplin_enabled = body.joplin_enabled
    if body.joplin_db_path is not None:
        cfg.joplin_db_path = body.joplin_db_path
    from apscheduler.jobstores.base import JobLookupError

    scheduler = ctx.scheduler
    if body.journal_schedule is not None:
        cfg.journal_schedule = ScheduleConfig(hour=body.journal_schedule.hour, minute=body.journal_schedule.minute)
        if scheduler:
            try:
                scheduler.reschedule_job("journal_job", trigger="cron", hour=cfg.journal_schedule.hour, minute=cfg.journal_schedule.minute)
            except JobLookupError:
                logger.warning("journal_job not found in scheduler; schedule saved but not live-applied")
    if body.blog_schedule is not None:
        cfg.blog_schedule = BlogScheduleConfig(
            frequency=body.blog_schedule.frequency,
            hour=body.blog_schedule.hour,
            minute=body.blog_schedule.minute,
            day=body.blog_schedule.day,
            days_of_week=body.blog_schedule.days_of_week,
        )
        if scheduler:
            try:
                scheduler.reschedule_job("blog_job", trigger="cron", **blog_cron_kwargs(cfg.blog_schedule))
            except JobLookupError:
                logger.warning("blog_job not found in scheduler; schedule saved but not live-applied")
    save_config(cfg)
    if body.chat_provider is not None or body.embed_provider is not None:
        await rebuild_ai_clients(ctx)
    return {"ok": True}


@router.post("/settings/paused")
async def set_paused(paused: bool, ctx: AppContext = Depends(get_context)):
    cfg = load_config()
    cfg.paused = paused
    save_config(cfg)
    ctx.paused = paused
    return {"ok": True, "paused": paused}


@router.get("/settings/exclusions")
async def list_exclusions():
    async with get_conn() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT app_name, added_at FROM app_exclusions ORDER BY app_name")
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/settings/exclusions")
async def add_exclusion(body: ExclusionRequest, ctx: AppContext = Depends(get_context)):
    async with get_conn() as conn:
        try:
            await conn.execute("INSERT INTO app_exclusions (app_name) VALUES (?)", (body.app_name,))
            await conn.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(409, f"{body.app_name} is already excluded")
    ctx.exclusions_dirty = True
    return {"ok": True}


@router.delete("/settings/exclusions/{app_name}")
async def remove_exclusion(app_name: str, ctx: AppContext = Depends(get_context)):
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM app_exclusions WHERE app_name = ?", (app_name,)
        )
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"{app_name} is not excluded")
    ctx.exclusions_dirty = True
    return {"ok": True}


@router.post("/settings/resync-chroma")
async def resync_chroma(ctx: AppContext = Depends(get_context)):
    """Backfill all activities with summaries that are not yet in ChromaDB."""
    from brn_daemon.embeddings import EmbeddingService
    from brn_daemon.providers import make_embed_client

    async def _run_backfill() -> int:
        embed_client = make_embed_client()
        chroma = ctx.chroma_store
        if chroma is None:
            from brn_daemon.embeddings import ChromaStore
            chroma = ChromaStore()
        service = EmbeddingService(embed_client=embed_client, chroma_store=chroma)
        synced = 0
        async with get_conn() as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """SELECT a.id, a.summary, a.task_category, a.productivity_state,
                          a.tags, a.started_at, c.app_name
                   FROM activities a
                   LEFT JOIN captures c ON c.id = a.capture_id
                   WHERE a.summary IS NOT NULL AND a.summary != ''
                   AND (a.chroma_id IS NULL OR a.chroma_id = '')
                   ORDER BY a.started_at"""
            )
            rows = await cur.fetchall()
        from brn_daemon.timeutil import utc_iso_to_local_date
        BATCH = 64
        batch: list[dict] = []
        for row in rows:
            metadata = {
                "timestamp": row["started_at"] or "",
                "app_name": row["app_name"] or "",
                "tags": row["tags"] or "",
                "date": utc_iso_to_local_date(row["started_at"]),
                "task_category": row["task_category"] or "other",
                "productivity_state": row["productivity_state"] or "idle",
                "source": "activity",
            }
            batch.append({"activity_id": row["id"], "summary": row["summary"], "metadata": metadata})
            if len(batch) >= BATCH:
                synced += await service.embed_activities_batch(batch)
                batch = []
        if batch:
            synced += await service.embed_activities_batch(batch)
        return synced

    _spawn(_run_backfill())
    return {"ok": True, "message": "ChromaDB re-sync started in background"}


@router.get("/settings/chroma-status")
async def chroma_status(ctx: AppContext = Depends(get_context)):
    """Return counts of total activities vs embedded ones."""
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT COUNT(*) FROM activities WHERE summary IS NOT NULL AND summary != ''"
        )
        total = (await cur.fetchone() or (0,))[0]
        cur = await conn.execute(
            "SELECT COUNT(*) FROM activities WHERE chroma_id IS NOT NULL AND chroma_id != ''"
        )
        embedded = (await cur.fetchone() or (0,))[0]
    chroma = ctx.chroma_store
    if chroma is None:
        from brn_daemon.embeddings import ChromaStore
        chroma = ChromaStore()
    chroma_count = await asyncio.get_event_loop().run_in_executor(None, chroma.collection.count)
    return {"total_activities": total, "embedded": embedded, "chroma_count": chroma_count}


# ── Screenshot encryption ────────────────────────────────────────────────────

class ScreenshotPasswordSet(BaseModel):
    password: str
    encrypt_existing: bool = True


class ScreenshotPasswordChange(BaseModel):
    old_password: str
    new_password: str


class ScreenshotPasswordDisable(BaseModel):
    password: str
    decrypt_existing: bool = True


@router.post("/settings/screenshot-password")
async def set_screenshot_password_route(body: ScreenshotPasswordSet, ctx: AppContext = Depends(get_context)):
    """Initialise screenshot encryption. Generates a salt, derives the key, persists the
    verifier to ``~/.2brn/encryption.json``, stores the password in the OS keychain, and
    (optionally) encrypts every existing screenshot in the background.
    """
    if is_initialised():
        raise HTTPException(409, "Screenshot encryption is already configured. Use PUT to change it or DELETE to disable it.")
    if not body.password or len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    key = initialize_encryption(body.password)
    set_screenshot_password(body.password)
    ctx.screenshot_key = key

    if body.encrypt_existing:
        async def _bulk_encrypt():
            try:
                logger.info("Encrypting existing screenshots in background…")
                ok, fail = await asyncio.get_event_loop().run_in_executor(
                    None, encrypt_existing_screenshots, key
                )
                rows = await mark_captures_encrypted()
                logger.info("Bulk encrypt complete: %d ok, %d failed, %d DB rows updated", ok, fail, rows)
            except Exception:
                logger.exception("Bulk encrypt failed")
        _spawn(_bulk_encrypt())

    return {"ok": True, "message": "Screenshot encryption enabled"}


@router.put("/settings/screenshot-password")
async def change_screenshot_password_route(body: ScreenshotPasswordChange, ctx: AppContext = Depends(get_context)):
    """Change the screenshot password. Verifies the old password against the stored verifier,
    then re-encrypts every ``.jpg.enc`` file in the background with the new key.
    """
    state = load_encryption_state()
    if state is None:
        raise HTTPException(404, "Screenshot encryption is not configured")
    if not body.new_password or len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")

    old_key = verify_password(body.old_password, state)
    if old_key is None:
        raise HTTPException(401, "Current password is incorrect")

    # Build a new state with a new salt + verifier under the new password.
    import os as _os

    from brn_daemon.encryption import (
        SALT_LENGTH,
        VERIFIER_PLAINTEXT,
        EncryptionState,  # noqa: F401  (constants only)
        derive_key,
        encrypt_bytes,
        save_encryption_state,
    )
    new_salt = _os.urandom(SALT_LENGTH)
    new_key = derive_key(body.new_password, new_salt)
    new_verifier = encrypt_bytes(VERIFIER_PLAINTEXT, new_key)
    save_encryption_state(EncryptionState(salt=new_salt, verifier=new_verifier))
    set_screenshot_password(body.new_password)

    ctx.screenshot_key = new_key

    async def _bulk_reencrypt():
        try:
            logger.info("Re-encrypting existing screenshots in background…")
            ok, fail = await asyncio.get_event_loop().run_in_executor(
                None, re_encrypt_all_screenshots, old_key, new_key
            )
            logger.info("Bulk re-encrypt complete: %d ok, %d failed", ok, fail)
        except Exception:
            logger.exception("Bulk re-encrypt failed")
    _spawn(_bulk_reencrypt())

    return {"ok": True, "message": "Screenshot password changed"}


@router.delete("/settings/screenshot-password")
async def disable_screenshot_password_route(body: ScreenshotPasswordDisable, ctx: AppContext = Depends(get_context)):
    """Disable screenshot encryption. Verifies the password, decrypts every ``.jpg.enc`` file
    back to plaintext (optionally), removes the verifier and the keychain entry.
    """
    state = load_encryption_state()
    if state is None:
        raise HTTPException(404, "Screenshot encryption is not configured")

    key = verify_password(body.password, state)
    if key is None:
        raise HTTPException(401, "Current password is incorrect")

    if body.decrypt_existing:
        # Block this request until decryption completes — the user is intentionally winding down
        # encryption and may want to verify their files are readable before they leave the page.
        try:
            ok, fail = await asyncio.get_event_loop().run_in_executor(
                None, decrypt_all_screenshots, key
            )
            await mark_captures_decrypted()
            logger.info("Bulk decrypt complete: %d ok, %d failed", ok, fail)
        except Exception:
            logger.exception("Bulk decrypt failed")

    delete_encryption_state()
    delete_screenshot_password()
    ctx.screenshot_key = None

    return {"ok": True, "message": "Screenshot encryption disabled"}
