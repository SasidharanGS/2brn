from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class JournalResponse(BaseModel):
    date: str
    content: str | None
    generated_at: str | None
    edited_by_user: bool

class JournalUpdateRequest(BaseModel):
    content: str

@router.get("/journal/{date}", response_model=JournalResponse)
async def get_journal(date: str):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT date, content, generated_at, edited_by_user FROM journals WHERE date = ?",
            (date,)
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, f"No journal for {date}")
    return JournalResponse(**dict(row))

@router.post("/journal/{date}/generate")
async def generate_journal(date: str):
    from brn_daemon.main import app_state
    gen = app_state.get("journal_generator")
    if not gen:
        raise HTTPException(503, "Journal generator not available")

    generating: set = app_state.setdefault("journal_generating", set())
    if date in generating:
        raise HTTPException(409, f"Journal for {date} is already being generated")

    generating.add(date)
    try:
        from datetime import date as dt_date
        target = dt_date.fromisoformat(date)
        content = await gen.generate(target_date=target)
    finally:
        generating.discard(date)

    return {"ok": True, "generated": content is not None}

@router.put("/journal/{date}")
async def update_journal(date: str, body: JournalUpdateRequest):
    from datetime import datetime, timezone
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """INSERT INTO journals (date, content, generated_at, edited_by_user)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(date) DO UPDATE SET
                 content = excluded.content,
                 edited_by_user = 1""",
            (date, body.content, datetime.now(timezone.utc).isoformat())
        )
        await conn.commit()
    return {"ok": True}
