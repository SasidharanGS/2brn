from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class StatusResponse(BaseModel):
    status: str  # "capturing" | "paused" | "error"
    capture_count_today: int
    last_captured_at: str | None
    daemon_version: str

@router.get("/status", response_model=StatusResponse)
async def get_status():
    from brn_daemon.main import app_state
    return StatusResponse(
        status="paused" if app_state["paused"] else "capturing",  # type: ignore[typeddict-item]
        capture_count_today=app_state.get("capture_count_today", 0),
        last_captured_at=app_state.get("last_captured_at"),
        daemon_version="0.1.0",
    )
