import asyncio
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context
from brn_daemon.db import get_conn
from brn_daemon.encryption import ENCRYPTED_EXT, decrypt_bytes
from brn_daemon.timeutil import local_day_bounds_utc

router = APIRouter()


class CaptureRecord(BaseModel):
    id: int
    captured_at: str
    app_name: str | None
    window_title: str | None
    file_path: str | None
    trigger: str | None
    monitor_index: int | None
    is_encrypted: bool = False


@router.get("/captures", response_model=list[CaptureRecord])
async def get_captures(date: str = Query(..., description="YYYY-MM-DD")):
    try:
        lo, hi = local_day_bounds_utc(date)
    except ValueError:
        raise HTTPException(400, f"Invalid date '{date}', expected YYYY-MM-DD")
    async with get_conn() as conn:
        conn.row_factory = aiosqlite.Row
        # Range bounds (not date(captured_at)) so idx_captures_captured_at is used,
        # and local-day aware to match the rest of the app (see timeutil).
        cur = await conn.execute(
            "SELECT id, captured_at, app_name, window_title, file_path, trigger, monitor_index "
            "FROM captures WHERE captured_at >= ? AND captured_at <= ? ORDER BY captured_at",
            (lo, hi)
        )
        rows = await cur.fetchall()
    return [
        CaptureRecord(**dict(r), is_encrypted=bool(r["file_path"] and r["file_path"].endswith(ENCRYPTED_EXT)))
        for r in rows
    ]


@router.get("/captures/{capture_id}/image")
async def get_capture_image(capture_id: int, ctx: AppContext = Depends(get_context)) -> Response:
    """Stream the JPEG bytes for a capture. Decrypts on the fly when the file is encrypted."""
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT file_path FROM captures WHERE id = ?", (capture_id,)
        )
        row = await cur.fetchone()
    if row is None or not row[0]:
        raise HTTPException(404, "Capture not found")

    path = Path(row[0])
    if not path.exists():
        raise HTTPException(404, "Image file missing from disk")

    # Read (and decrypt) off the event loop — these are blocking disk/CPU work.
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, path.read_bytes)
    if not str(path).endswith(ENCRYPTED_EXT):
        return Response(raw, media_type="image/jpeg")

    # Encrypted — need the in-memory key.
    key = ctx.screenshot_key
    if key is None:
        raise HTTPException(503, "Image is encrypted but no screenshot password is loaded")
    try:
        plaintext = await loop.run_in_executor(None, decrypt_bytes, raw, key)
    except Exception as exc:
        raise HTTPException(500, f"Failed to decrypt image: {exc}") from exc
    return Response(plaintext, media_type="image/jpeg")
