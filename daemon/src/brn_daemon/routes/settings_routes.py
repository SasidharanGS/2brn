from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from brn_daemon.config import (
    load_config, save_config,
    get_chat_api_key, get_embed_api_key,
    set_chat_api_key, set_embed_api_key,
)
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()


class ProviderConfigOut(BaseModel):
    type: str
    base_url: str
    model: str
    extra_headers: dict = {}


class SettingsResponse(BaseModel):
    chat_provider: ProviderConfigOut
    embed_provider: ProviderConfigOut
    has_chat_key: bool
    has_embed_key: bool
    capture_interval_seconds: int
    purge_months: int
    paused: bool
    blog_mirror_enabled: bool


class ProviderConfigIn(BaseModel):
    type: str | None = None
    base_url: str | None = None
    model: str | None = None
    extra_headers: dict | None = None
    api_key: str | None = None


class SettingsUpdateRequest(BaseModel):
    chat_provider: ProviderConfigIn | None = None
    embed_provider: ProviderConfigIn | None = None
    capture_interval_seconds: int | None = None
    purge_months: int | None = None
    blog_mirror_enabled: bool | None = None


class ExclusionRequest(BaseModel):
    app_name: str


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    cfg = load_config()
    cp = cfg.chat_provider
    ep = cfg.embed_provider
    return SettingsResponse(
        chat_provider=ProviderConfigOut(type=cp.type, base_url=cp.base_url, model=cp.model, extra_headers=cp.extra_headers),
        embed_provider=ProviderConfigOut(type=ep.type, base_url=ep.base_url, model=ep.model, extra_headers=ep.extra_headers),
        has_chat_key=bool(get_chat_api_key()),
        has_embed_key=bool(get_embed_api_key()),
        capture_interval_seconds=cfg.capture_interval_seconds,
        purge_months=cfg.purge_months,
        paused=cfg.paused,
        blog_mirror_enabled=cfg.blog_mirror_enabled,
    )


@router.put("/settings")
async def update_settings(body: SettingsUpdateRequest):
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
    if body.purge_months is not None:
        cfg.purge_months = body.purge_months
    if body.blog_mirror_enabled is not None:
        cfg.blog_mirror_enabled = body.blog_mirror_enabled
    save_config(cfg)
    return {"ok": True}


@router.post("/settings/paused")
async def set_paused(paused: bool):
    from brn_daemon.main import app_state
    cfg = load_config()
    cfg.paused = paused
    save_config(cfg)
    app_state["paused"] = paused
    return {"ok": True, "paused": paused}


@router.get("/settings/exclusions")
async def list_exclusions():
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT app_name, added_at FROM app_exclusions ORDER BY app_name")
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/settings/exclusions")
async def add_exclusion(body: ExclusionRequest):
    from brn_daemon.main import app_state
    async with aiosqlite.connect(get_db_path()) as conn:
        try:
            await conn.execute("INSERT INTO app_exclusions (app_name) VALUES (?)", (body.app_name,))
            await conn.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(409, f"{body.app_name} is already excluded")
    app_state["exclusions_dirty"] = True
    return {"ok": True}


@router.post("/settings/resync-chroma")
async def resync_chroma():
    """Backfill all activities with summaries that are not yet in ChromaDB."""
    import asyncio
    from brn_daemon.main import app_state
    from brn_daemon.embeddings import EmbeddingService
    from brn_daemon.gateway import make_gateway_client

    async def _run_backfill() -> int:
        gateway = make_gateway_client()
        chroma = app_state.get("chroma_store")
        if chroma is None:
            from brn_daemon.embeddings import ChromaStore
            chroma = ChromaStore()
        service = EmbeddingService(gateway=gateway, chroma_store=chroma)
        synced = 0
        async with aiosqlite.connect(get_db_path()) as conn:
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
        for row in rows:
            date_str = row["started_at"][:10] if row["started_at"] else ""
            metadata = {
                "timestamp": row["started_at"] or "",
                "app_name": row["app_name"] or "",
                "tags": row["tags"] or "",
                "date": date_str,
                "task_category": row["task_category"] or "other",
                "productivity_state": row["productivity_state"] or "idle",
            }
            await service.embed_activity(
                activity_id=row["id"],
                summary=row["summary"],
                metadata=metadata,
            )
            synced += 1
        return synced

    asyncio.create_task(_run_backfill())
    return {"ok": True, "message": "ChromaDB re-sync started in background"}


@router.get("/settings/chroma-status")
async def chroma_status():
    """Return counts of total activities vs embedded ones."""
    from brn_daemon.main import app_state
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT COUNT(*) FROM activities WHERE summary IS NOT NULL AND summary != ''"
        )
        total = (await cur.fetchone())[0]
        cur = await conn.execute(
            "SELECT COUNT(*) FROM activities WHERE chroma_id IS NOT NULL AND chroma_id != ''"
        )
        embedded = (await cur.fetchone())[0]
    chroma = app_state.get("chroma_store")
    if chroma is None:
        from brn_daemon.embeddings import ChromaStore
        chroma = ChromaStore()
    chroma_count = chroma.collection.count()
    return {"total_activities": total, "embedded": embedded, "chroma_count": chroma_count}
