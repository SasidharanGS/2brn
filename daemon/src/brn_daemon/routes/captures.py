from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
import aiosqlite
from brn_daemon.db import get_db_path
from brn_daemon.encryption import ENCRYPTED_EXT, decrypt_bytes

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
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT id, captured_at, app_name, window_title, file_path, trigger, monitor_index "
            "FROM captures WHERE date(captured_at) = ? ORDER BY captured_at",
            (date,)
        )
        rows = await cur.fetchall()
    return [
        CaptureRecord(**dict(r), is_encrypted=bool(r["file_path"] and r["file_path"].endswith(ENCRYPTED_EXT)))
        for r in rows
    ]


@router.get("/captures/{capture_id}/image")
async def get_capture_image(capture_id: int) -> Response:
    """Stream the JPEG bytes for a capture. Decrypts on the fly when the file is encrypted."""
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT file_path FROM captures WHERE id = ?", (capture_id,)
        )
        row = await cur.fetchone()
    if row is None or not row[0]:
        raise HTTPException(404, "Capture not found")

    path = Path(row[0])
    if not path.exists():
        raise HTTPException(404, "Image file missing from disk")

    if not str(path).endswith(ENCRYPTED_EXT):
        return Response(path.read_bytes(), media_type="image/jpeg")

    # Encrypted — need the in-memory key.
    from brn_daemon.main import app_state
    key = app_state.get("screenshot_key")
    if key is None:
        raise HTTPException(503, "Image is encrypted but no screenshot password is loaded")
    try:
        plaintext = decrypt_bytes(path.read_bytes(), key)
    except Exception as exc:
        raise HTTPException(500, f"Failed to decrypt image: {exc}") from exc
    return Response(plaintext, media_type="image/jpeg")
