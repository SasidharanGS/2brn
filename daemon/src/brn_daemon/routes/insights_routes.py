from fastapi import APIRouter, Query
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()


def _day_bounds(date: str) -> tuple[str, str]:
    """Return (start, exclusive_end) ISO strings for a given YYYY-MM-DD date.
    Uses range bounds so the idx_activities_started_at index can be used
    instead of applying date() to every row.
    """
    return f"{date}T00:00:00", f"{date}T23:59:59.999999"


@router.get("/insights/daily")
async def daily_insights(date: str = Query(...)):
    lo, hi = _day_bounds(date)
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """SELECT task_category, COUNT(*) as count,
               AVG(task_category_confidence) as avg_confidence
               FROM activities WHERE started_at >= ? AND started_at <= ?
               GROUP BY task_category ORDER BY count DESC""",
            (lo, hi)
        )
        categories = [{"task_category": r[0], "count": r[1], "avg_confidence": r[2]}
                      for r in await cur.fetchall()]
        cur = await conn.execute(
            """SELECT productivity_state, COUNT(*) as count
               FROM activities WHERE started_at >= ? AND started_at <= ?
               GROUP BY productivity_state ORDER BY count DESC""",
            (lo, hi)
        )
        states = [{"productivity_state": r[0], "count": r[1]} for r in await cur.fetchall()]
        cap_lo = f"{date}T00:00:00"
        cap_hi = f"{date}T23:59:59.999999"
        cur = await conn.execute(
            """SELECT app_name, COUNT(*) as count FROM captures
               WHERE captured_at >= ? AND captured_at <= ? AND app_name IS NOT NULL
               GROUP BY app_name ORDER BY count DESC LIMIT 10""",
            (cap_lo, cap_hi)
        )
        top_apps = [{"app_name": r[0], "count": r[1]} for r in await cur.fetchall()]
    return {"date": date, "categories": categories, "productivity_states": states, "top_apps": top_apps}


@router.get("/insights/weekly")
async def weekly_insights(week_start: str = Query(..., description="YYYY-MM-DD of Monday")):
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """SELECT date(started_at) as day, task_category, COUNT(*) as count
               FROM activities
               WHERE started_at >= ? AND started_at < date(?, '+7 days')
               GROUP BY day, task_category ORDER BY day""",
            (f"{week_start}T00:00:00", week_start)
        )
        rows = await cur.fetchall()
    return {"week_start": week_start,
            "data": [{"day": r[0], "task_category": r[1], "count": r[2]} for r in rows]}
