"""Note ingestion for the mobile Share-sheet ("Save to 2brn").

A shared web page / text selection / note is persisted to the additive
``shared_notes`` table (so it survives a Chroma rebuild and can be listed on the
phone) and embedded into the ``note_memories`` collection (so it shows up in chat
RAG alongside Joplin notes). Persistence is the guaranteed step; embedding is
best-effort and heals on a future resync if the provider is offline.
"""
import asyncio
import logging
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from brn_daemon.context import AppContext, get_context
from brn_daemon.db import get_conn, get_db_path
from brn_daemon.timeutil import utc_iso_to_local_date, utc_now_iso

logger = logging.getLogger(__name__)
router = APIRouter()


class NoteIngestRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str | None = None
    source_url: str | None = None
    tags: str | None = None


class NoteIngestResponse(BaseModel):
    ok: bool
    id: int
    embedded: bool


class SharedNote(BaseModel):
    id: int
    title: str | None
    text: str
    source_url: str | None
    tags: str | None
    source: str
    embedded: bool
    created_at: str


async def _try_embed_note(
    ctx: AppContext, note_id: int, title: str | None, text: str,
    source_url: str | None, created_at: str,
) -> bool:
    """Embed a shared note into note_memories. Best-effort — a row is always saved;
    if embedding is unavailable or fails the note stays ``embedded=0``."""
    embed_client: Any = ctx.embed_client
    chroma = ctx.chroma_store
    if embed_client is None or chroma is None:
        return False
    try:
        embed_input = "\n".join(p for p in (title, text, source_url) if p)
        embedding = await embed_client.embed(embed_input)
        doc_id = f"shared-note-{note_id}"
        metadata = {
            "source": "mobile-share",
            "timestamp": created_at,
            "date": utc_iso_to_local_date(created_at),
            "title": title or "Shared note",
            "notebook": source_url or "",
        }
        await chroma.add_note(doc_id=doc_id, text=text, metadata=metadata, embedding=embedding)
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                "UPDATE shared_notes SET chroma_id = ?, embedded = 1 WHERE id = ?",
                (doc_id, note_id),
            )
            await conn.commit()
        return True
    except Exception:
        logger.exception("Failed to embed shared note %d", note_id)
        return False


@router.post("/ingest/note", response_model=NoteIngestResponse)
async def ingest_note(body: NoteIngestRequest, ctx: AppContext = Depends(get_context)):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "text must not be empty")
    title = (body.title or "").strip() or None
    source_url = (body.source_url or "").strip() or None
    tags = (body.tags or "").strip() or None
    created_at = utc_now_iso()

    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO shared_notes (title, text, source_url, tags, source, embedded, created_at) "
            "VALUES (?, ?, ?, ?, 'mobile-share', 0, ?)",
            (title, text, source_url, tags, created_at),
        )
        await conn.commit()
        note_id: int = cur.lastrowid  # type: ignore[assignment]

    embedded = await _try_embed_note(ctx, note_id, title, text, source_url, created_at)
    return NoteIngestResponse(ok=True, id=note_id, embedded=embedded)


@router.get("/ingest/notes", response_model=list[SharedNote])
async def list_notes(limit: int = 50):
    limit = max(1, min(limit, 200))
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT id, title, text, source_url, tags, source, embedded, created_at "
            "FROM shared_notes ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
    return [
        SharedNote(
            id=r["id"],
            title=r["title"],
            text=r["text"],
            source_url=r["source_url"],
            tags=r["tags"],
            source=r["source"],
            embedded=bool(r["embedded"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.delete("/ingest/notes/{note_id}")
async def delete_note(note_id: int, ctx: AppContext = Depends(get_context)):
    async with get_conn() as conn:
        cur = await conn.execute("SELECT chroma_id FROM shared_notes WHERE id = ?", (note_id,))
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(404, "note not found")
        chroma_id = row[0]
        await conn.execute("DELETE FROM shared_notes WHERE id = ?", (note_id,))
        await conn.commit()

    if chroma_id:
        chroma = ctx.chroma_store
        if chroma is not None:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, lambda: chroma.note_collection.delete(ids=[chroma_id])
                )
            except Exception:
                logger.exception("Failed to delete shared note %d from chroma", note_id)
    return {"ok": True}
