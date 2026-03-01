from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import aiosqlite
from datetime import datetime, timezone
from brn_daemon.db import get_db_path

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
    async with aiosqlite.connect(get_db_path()) as conn:
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
async def generate_blog_post(date: str):
    from brn_daemon.main import app_state
    gen = app_state.get("blog_generator")
    if not gen:
        raise HTTPException(503, "Blog generator not available")

    generating: set = app_state.setdefault("blog_generating", set())
    if date in generating:
        raise HTTPException(409, f"Blog post for {date} is already being generated")

    generating.add(date)
    try:
        from datetime import date as dt_date
        target = dt_date.fromisoformat(date)
        content = await gen.generate(target_date=target)
    finally:
        generating.discard(date)

    return {"ok": True, "generated": content is not None}


@router.put("/blog/{date}")
async def update_blog_post(date: str, body: BlogPostUpdateRequest):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """INSERT INTO blog_posts (date, content, generated_at, edited_by_user)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(date) DO UPDATE SET
                 content = excluded.content,
                 edited_by_user = 1""",
            (date, body.content, now)
        )
        await conn.commit()
    return {"ok": True}
