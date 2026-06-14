from datetime import UTC

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context
from brn_daemon.db import get_conn

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
    async with get_conn() as conn:
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
async def generate_journal(date: str, ctx: AppContext = Depends(get_context)):
    gen = ctx.journal_generator
    if not gen:
        raise HTTPException(503, "Journal generator not available")

    from datetime import date as dt_date
    try:
        target = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, f"Invalid date '{date}', expected YYYY-MM-DD")

    generating = ctx.journal_generating
    if date in generating:
        raise HTTPException(409, f"Journal for {date} is already being generated")

    generating.add(date)
    try:
        content = await gen.generate(target_date=target)
    finally:
        generating.discard(date)

    return {"ok": True, "generated": content is not None}

@router.put("/journal/{date}")
async def update_journal(date: str, body: JournalUpdateRequest):
    from datetime import datetime
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO journals (date, content, generated_at, edited_by_user)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(date) DO UPDATE SET
                 content = excluded.content,
                 generated_at = excluded.generated_at,
                 edited_by_user = 1""",
            (date, body.content, datetime.now(UTC).isoformat())
        )
        await conn.commit()
    return {"ok": True}
