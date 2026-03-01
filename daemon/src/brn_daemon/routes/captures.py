from fastapi import APIRouter, Query
from pydantic import BaseModel
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class CaptureRecord(BaseModel):
    id: int
    captured_at: str
    app_name: str | None
    window_title: str | None
    file_path: str | None
    trigger: str | None
    monitor_index: int | None

@router.get("/captures", response_model=list[CaptureRecord])
async def get_captures(date: str = Query(..., description="YYYY-MM-DD")):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT id, captured_at, app_name, window_title, file_path, trigger, monitor_index "
            "FROM captures WHERE date(captured_at) = ? ORDER BY captured_at",
            (date,)
        )
        rows = await cur.fetchall()
    return [CaptureRecord(**dict(r)) for r in rows]
