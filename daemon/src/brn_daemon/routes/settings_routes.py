from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from brn_daemon.config import load_config, save_config, get_gateway_token, set_gateway_token
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class SettingsResponse(BaseModel):
    gateway_url: str
    llm_model: str
    embed_model: str
    capture_interval_seconds: int
    purge_months: int
    paused: bool
    has_token: bool
    blog_mirror_enabled: bool

class SettingsUpdateRequest(BaseModel):
    gateway_url: str | None = None
    gateway_token: str | None = None
    llm_model: str | None = None
    embed_model: str | None = None
    capture_interval_seconds: int | None = None
    purge_months: int | None = None
    blog_mirror_enabled: bool | None = None

class ExclusionRequest(BaseModel):
    app_name: str

@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    cfg = load_config()
    return SettingsResponse(
        gateway_url=cfg.gateway_url,
        llm_model=cfg.llm_model,
        embed_model=cfg.embed_model,
        capture_interval_seconds=cfg.capture_interval_seconds,
        purge_months=cfg.purge_months,
        paused=cfg.paused,
        has_token=bool(get_gateway_token()),
        blog_mirror_enabled=cfg.blog_mirror_enabled,
    )

@router.put("/settings")
async def update_settings(body: SettingsUpdateRequest):
    cfg = load_config()
    if body.gateway_url is not None:
        cfg.gateway_url = body.gateway_url
    if body.llm_model is not None:
        cfg.llm_model = body.llm_model
    if body.embed_model is not None:
        cfg.embed_model = body.embed_model
    if body.capture_interval_seconds is not None:
        cfg.capture_interval_seconds = body.capture_interval_seconds
    if body.purge_months is not None:
        cfg.purge_months = body.purge_months
    if body.blog_mirror_enabled is not None:
        cfg.blog_mirror_enabled = body.blog_mirror_enabled
    if body.gateway_token is not None:
        try:
            set_gateway_token(body.gateway_token)
        except RuntimeError as exc:
            raise HTTPException(500, f"Token save failed: {exc}") from exc
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

    # Run in background so the HTTP response returns immediately
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
    # Reuse the shared ChromaStore instance — avoids opening ChromaDB files on every request
    chroma = app_state.get("chroma_store")
    if chroma is None:
        from brn_daemon.embeddings import ChromaStore
        chroma = ChromaStore()
    chroma_count = chroma.collection.count()
    return {"total_activities": total, "embedded": embedded, "chroma_count": chroma_count}

