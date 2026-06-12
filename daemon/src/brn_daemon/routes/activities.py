import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from brn_daemon.db import get_db_path

router = APIRouter()

class ActivityRecord(BaseModel):
    id: int
    capture_id: int | None
    started_at: str
    summary: str | None
    tags: str | None
    task_category: str | None
    task_category_confidence: float | None
    productivity_state: str | None
    productivity_confidence: float | None
    category_overridden_by_user: bool

@router.get("/activities", response_model=list[ActivityRecord])
async def get_activities(
    date: str = Query(None),
    task_category: str = Query(None),
    productivity_state: str = Query(None),
):
    conditions = []
    params = []
    if date:
        # Use range bounds instead of date() function so idx_activities_started_at is used
        conditions.append("started_at >= ?")
        conditions.append("started_at <= ?")
        params.append(f"{date}T00:00:00")
        params.append(f"{date}T23:59:59.999999")
    if task_category:
        conditions.append("task_category = ?")
        params.append(task_category)
    if productivity_state:
        conditions.append("productivity_state = ?")
        params.append(productivity_state)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            f"SELECT id, capture_id, started_at, summary, tags, "
            f"task_category, task_category_confidence, productivity_state, "
            f"productivity_confidence, category_overridden_by_user "
            f"FROM activities {where} ORDER BY started_at",
            params
        )
        rows = await cur.fetchall()
    return [
        ActivityRecord(**{
            **dict(r),
            "started_at": r["started_at"] + "Z" if r["started_at"] and not r["started_at"].endswith("Z") else r["started_at"],
        })
        for r in rows
    ]

class BackfillRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=365)
    # Opt-in: also classify sparse-text captures (videos, images) from their
    # app/window metadata — spends ~1 LLM call per distinct window title.
    include_sparse: bool = False


@router.post("/activities/backfill")
async def backfill_activities(body: BackfillRequest | None = None):
    """Re-run inference for captures with readable OCR text but no activity.

    Repairs the permanent classification gaps left by provider outages and
    inference-queue overflows; such captures otherwise stay 'unclassified'
    in the timeline forever. Also runs automatically at daemon startup.
    """
    from brn_daemon.main import app_state
    queue = app_state.get("inference_queue")
    if queue is None:
        raise HTTPException(503, "Inference queue is not running")
    body = body or BackfillRequest()
    result = await queue.backfill_unclassified(days=body.days, include_sparse=body.include_sparse)
    return {"ok": True, **result}


class OverrideRequest(BaseModel):
    task_category: str
    productivity_state: str


@router.patch("/activities/{activity_id}/override")
async def override_activity(activity_id: int, body: OverrideRequest):
    from brn_daemon.inference import VALID_CATEGORIES, VALID_STATES
    if body.task_category not in VALID_CATEGORIES or body.productivity_state not in VALID_STATES:
        raise HTTPException(400, "Invalid category or state")
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "UPDATE activities SET task_category = ?, productivity_state = ?, "
            "category_overridden_by_user = 1 WHERE id = ?",
            (body.task_category, body.productivity_state, activity_id)
        )
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "Activity not found")
    return {"ok": True}
