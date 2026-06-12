"""GET /sessions — activity samples folded into duration blocks (see sessions.py)."""

import asyncio
from datetime import UTC, datetime

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from brn_daemon.config import load_config
from brn_daemon.db import get_db_path
from brn_daemon.sessions import SessionPolicy, compute_totals, sessionize
from brn_daemon.timeutil import local_day_bounds_utc

router = APIRouter()

_SAMPLES_SQL = """
    SELECT a.started_at, a.summary, a.task_category, a.productivity_state,
           COALESCE(a.app_name_override, c.app_name) AS app_name,
           COALESCE(c.monitor_index, 0) AS monitor_index
    FROM activities a
    LEFT JOIN captures c ON a.capture_id = c.id
    WHERE a.started_at >= ? AND a.started_at <= ?
    ORDER BY a.started_at
"""


def _iso_z(dt: datetime) -> str:
    return dt.isoformat() + "Z"


@router.get("/sessions")
async def get_sessions(date: str = Query(..., description="Local day, YYYY-MM-DD")):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from None
    lo, hi = local_day_bounds_utc(date)

    cfg = await asyncio.get_event_loop().run_in_executor(None, load_config)
    interval = cfg.capture_interval_seconds
    policy = SessionPolicy(
        capture_interval_seconds=interval,
        gap_split_seconds=max(180, 3 * interval),
    )

    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(_SAMPLES_SQL, (lo, hi))
        samples = [dict(r) for r in await cur.fetchall()]

    # Blocks never extend past the day or, for today, past the present moment.
    range_end = min(
        datetime.fromisoformat(hi),
        datetime.now(UTC).replace(tzinfo=None),
    )
    blocks = sessionize(samples, policy, range_end=range_end)

    return {
        "date": date,
        "capture_interval_seconds": policy.capture_interval_seconds,
        "gap_split_seconds": policy.gap_split_seconds,
        "blocks": [
            {
                "start": _iso_z(b.start),
                "end": _iso_z(b.end),
                "duration_seconds": b.duration_seconds,
                "monitor_index": b.monitor_index,
                "app_name": b.app_name,
                "task_category": b.task_category,
                "dominant_state": b.dominant_state,
                "sample_count": b.sample_count,
                "summary": b.summary,
            }
            for b in blocks
        ],
        "totals": compute_totals(blocks),
    }
