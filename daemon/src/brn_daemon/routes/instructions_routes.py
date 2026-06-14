from datetime import UTC, datetime

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context
from brn_daemon.db import get_conn

router = APIRouter()


class UserInstruction(BaseModel):
    id: int
    title: str
    body: str
    enabled: bool
    created_at: str


class CreateInstructionRequest(BaseModel):
    title: str
    body: str
    enabled: bool = True


class UpdateInstructionRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    enabled: bool | None = None


@router.get("/instructions", response_model=list[UserInstruction])
async def list_instructions():
    async with get_conn() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT id, title, body, enabled, created_at FROM user_instructions ORDER BY created_at ASC"
        )
        rows = await cur.fetchall()
    return [
        UserInstruction(
            id=r["id"],
            title=r["title"],
            body=r["body"],
            enabled=bool(r["enabled"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/instructions", response_model=UserInstruction, status_code=201)
async def create_instruction(body: CreateInstructionRequest, ctx: AppContext = Depends(get_context)):
    now = datetime.now(UTC).isoformat()
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO user_instructions (title, body, enabled, created_at) VALUES (?, ?, ?, ?)",
            (body.title, body.body, int(body.enabled), now),
        )
        await conn.commit()
        row_id: int = cur.lastrowid  # type: ignore[assignment]
    iq = ctx.inference_queue
    if iq is not None:
        iq.invalidate_instructions_cache()
    return UserInstruction(id=row_id, title=body.title, body=body.body, enabled=body.enabled, created_at=now)


@router.put("/instructions/{instruction_id}", response_model=UserInstruction)
async def update_instruction(instruction_id: int, body: UpdateInstructionRequest, ctx: AppContext = Depends(get_context)):
    async with get_conn() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT id, title, body, enabled, created_at FROM user_instructions WHERE id = ?",
            (instruction_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Instruction not found")
        new_title   = body.title   if body.title   is not None else row["title"]
        new_body    = body.body    if body.body    is not None else row["body"]
        new_enabled = body.enabled if body.enabled is not None else bool(row["enabled"])
        await conn.execute(
            "UPDATE user_instructions SET title = ?, body = ?, enabled = ? WHERE id = ?",
            (new_title, new_body, int(new_enabled), instruction_id),
        )
        await conn.commit()
    iq = ctx.inference_queue
    if iq is not None:
        iq.invalidate_instructions_cache()
    return UserInstruction(
        id=instruction_id,
        title=new_title,
        body=new_body,
        enabled=new_enabled,
        created_at=row["created_at"],
    )


@router.delete("/instructions/{instruction_id}", status_code=204)
async def delete_instruction(instruction_id: int, ctx: AppContext = Depends(get_context)):
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM user_instructions WHERE id = ?", (instruction_id,)
        )
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Instruction not found")
    iq = ctx.inference_queue
    if iq is not None:
        iq.invalidate_instructions_cache()
