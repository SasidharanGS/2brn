from fastapi import APIRouter, Depends
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context

router = APIRouter()

class StatusResponse(BaseModel):
    status: str  # "capturing" | "paused" | "error"
    capture_count_today: int
    last_captured_at: str | None
    daemon_version: str

@router.get("/status", response_model=StatusResponse)
async def get_status(ctx: AppContext = Depends(get_context)):
    return StatusResponse(
        status="paused" if ctx.paused else "capturing",
        capture_count_today=ctx.capture_count_today,
        last_captured_at=ctx.last_captured_at,
        daemon_version="0.1.0",
    )
