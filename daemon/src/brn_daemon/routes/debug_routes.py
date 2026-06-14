import asyncio

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context

router = APIRouter()


class LogsResponse(BaseModel):
    lines: list[dict]


class DebugStatusResponse(BaseModel):
    daemon: dict
    gateway: dict
    chroma: dict
    last_error: dict | None
    failed_capture_ids: list[int]


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    level: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    from brn_daemon.log_buffer import log_buffer
    return LogsResponse(lines=log_buffer.get(level=level, limit=limit))


@router.get("/debug/status", response_model=DebugStatusResponse)
async def get_debug_status(ctx: AppContext = Depends(get_context)):
    from brn_daemon.config import load_config

    cfg = await asyncio.get_event_loop().run_in_executor(None, load_config)

    # Daemon section — read from the app context
    _iq = ctx.inference_queue
    daemon_section = {
        "status": "paused" if ctx.paused else "capturing",
        "capture_count_today": ctx.capture_count_today,
        "last_captured_at": ctx.last_captured_at,
        "paused": bool(ctx.paused),
        "dropped_inferences": _iq.dropped_count if _iq is not None else 0,
        "inference_queue_depth": _iq.queue_depth if _iq is not None else 0,
    }

    # Gateway reachability — try /actuator/health with 3s timeout
    gateway_reachable = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            base = cfg.chat_provider.base_url.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            r = await client.get(f"{base}/actuator/health")
            gateway_reachable = r.status_code == 200
    except Exception:
        gateway_reachable = False

    gateway_section = {
        "url": cfg.chat_provider.base_url,
        "reachable": gateway_reachable,
        "model": cfg.chat_provider.model,
    }

    # Chroma counts
    chroma = ctx.chroma_store
    activity_count = 0
    note_count = 0
    if chroma is not None:
        try:
            loop = asyncio.get_event_loop()
            activity_count = await loop.run_in_executor(None, chroma.collection.count)
            note_count = await loop.run_in_executor(None, chroma.note_collection.count)
        except Exception:
            pass

    chroma_section = {
        "activity_memories": activity_count,
        "note_memories": note_count,
    }

    # Last error from log buffer
    from brn_daemon.log_buffer import log_buffer
    errors = log_buffer.get(level="ERROR", limit=500)
    last_error = errors[-1] if errors else None

    return DebugStatusResponse(
        daemon=daemon_section,
        gateway=gateway_section,
        chroma=chroma_section,
        last_error=last_error,
        failed_capture_ids=_iq.failed_capture_ids if _iq is not None else [],
    )
