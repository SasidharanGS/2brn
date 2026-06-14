from datetime import UTC, datetime

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context
from brn_daemon.db import get_conn

router = APIRouter()


class BlogPostResponse(BaseModel):
    date: str
    content: str | None
    generated_at: str | None
    edited_by_user: bool


class BlogPostUpdateRequest(BaseModel):
    content: str


@router.get("/blog/{date}", response_model=BlogPostResponse)
async def get_blog_post(date: str):
    async with get_conn() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT date, content, generated_at, edited_by_user FROM blog_posts WHERE date = ?",
            (date,)
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, f"No blog post for {date}")
    return BlogPostResponse(**dict(row))


@router.post("/blog/{date}/generate")
async def generate_blog_post(date: str, ctx: AppContext = Depends(get_context)):
    gen = ctx.blog_generator
    if not gen:
        raise HTTPException(503, "Blog generator not available")

    from datetime import date as dt_date
    try:
        target = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, f"Invalid date '{date}', expected YYYY-MM-DD")

    generating = ctx.blog_generating
    if date in generating:
        raise HTTPException(409, f"Blog post for {date} is already being generated")

    generating.add(date)
    try:
        content = await gen.generate(target_date=target)
    finally:
        generating.discard(date)

    return {"ok": True, "generated": content is not None}


@router.put("/blog/{date}")
async def update_blog_post(date: str, body: BlogPostUpdateRequest):
    now = datetime.now(UTC).isoformat()
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO blog_posts (date, content, generated_at, edited_by_user)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(date) DO UPDATE SET
                 content = excluded.content,
                 generated_at = excluded.generated_at,
                 edited_by_user = 1""",
            (date, body.content, now)
        )
        await conn.commit()
    return {"ok": True}
