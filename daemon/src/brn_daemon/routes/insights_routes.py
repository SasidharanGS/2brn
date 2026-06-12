from __future__ import annotations

import asyncio
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from brn_daemon.config import load_config
from brn_daemon.db import get_db_path
from brn_daemon.sessions import (
    UNCLASSIFIED,
    Block,
    SessionPolicy,
    compute_totals,
    fetch_samples,
    sessionize,
)
from brn_daemon.timeutil import local_day_bounds_utc, local_range_bounds_utc

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


PRODUCTIVE_STATES = ("productive", "focused")
DISTRACTED_STATES = ("distracted", "procrastinating")


def _pct(count: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round(count / total * 100, 1)


def _day_bounds(date: str) -> tuple[str, str]:
    """Return (start, end) naive-UTC bounds covering the LOCAL day `date`.

    Range bounds (not date()) so idx_activities_started_at is used, and
    local-day aware so buckets match the user's timezone (brn_daemon.timeutil).
    """
    return local_day_bounds_utc(date)


def _parse_date(date: str) -> datetime:
    try:
        return datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid date: {date}") from exc


def _period_range(date: str, period: str) -> tuple[str, str, int]:
    """Return (start_iso, end_iso, span_days) for the selected period.

    `date` is the anchor (the right-most day). Period values:
      day   → exactly that date (span_days = 1)
      week  → the 7 days ending on `date`
      month → the 30 days ending on `date`
    """
    _parse_date(date)  # validate format → 400 on bad input
    span = {"day": 1, "week": 7, "month": 30}.get(period)
    if span is None:
        raise HTTPException(status_code=400, detail=f"invalid period: {period}")
    start_iso, end_iso = local_range_bounds_utc(date, span)
    return start_iso, end_iso, span


def _baseline_range(date: str, period: str) -> tuple[str, str, int, str]:
    """Range for the baseline window used in `comparison`.

    Returns (start_iso, end_iso, n_periods, label) where n_periods is how
    many "current-period" lengths fit in the baseline — used to convert
    the baseline totals into a per-period average.
    """
    anchor = _parse_date(date)
    if period == "day":
        # 7 local days ending the day before the anchor day.
        base_end_date = (anchor - timedelta(days=1)).strftime("%Y-%m-%d")
        lo, hi = local_range_bounds_utc(base_end_date, 7)
        return lo, hi, 7, "7-day average"
    if period == "week":
        # 28 local days ending the day before the current 7-day window.
        base_end_date = (anchor - timedelta(days=7)).strftime("%Y-%m-%d")
        lo, hi = local_range_bounds_utc(base_end_date, 28)
        return lo, hi, 4, "4-week average"
    # month: 90 local days ending the day before the current 30-day window.
    base_end_date = (anchor - timedelta(days=30)).strftime("%Y-%m-%d")
    lo, hi = local_range_bounds_utc(base_end_date, 90)
    return lo, hi, 3, "3-month average"


# ---------------------------------------------------------------------------
# Recurring-activity clustering (token-set Jaccard)
# ---------------------------------------------------------------------------


_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "into", "this", "that",
        "are", "was", "were", "but", "not", "any", "all", "out", "via",
        "you", "your", "have", "has", "had", "been", "being", "their",
        "then", "than", "them", "they", "its", "it's", "an", "of", "on",
        "in", "to", "a", "is", "as", "at", "by", "or", "be",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(
        t for t in _TOKEN_RE.findall(text.lower())
        if len(t) >= 3 and t not in _STOPWORDS
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def _cluster_summaries(
    rows: Iterable[tuple[str, int]],
    *,
    threshold: float = 0.6,
) -> list[dict]:
    """Cluster (summary, count) rows by token-set Jaccard.

    First aggregates exact-duplicate summaries (cheap), then collapses
    near-duplicates with Jaccard ≥ threshold using union-find. Returns
    clusters sorted by total count desc, each as
    {canonical_summary, total_count, session_count, variants}.
    """
    # Pass 1: exact-summary aggregation.
    by_exact: dict[str, int] = defaultdict(int)
    for summary, count in rows:
        if not summary:
            continue
        by_exact[summary.strip()] += int(count)
    items = sorted(by_exact.items(), key=lambda kv: -kv[1])
    if not items:
        return []

    # Pass 2: token sets per distinct summary.
    tokens = [_tokenize(s) for s, _ in items]

    # Pass 3: union-find over near-duplicates.
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    n = len(items)
    for i in range(n):
        if not tokens[i]:
            continue
        for j in range(i + 1, n):
            if not tokens[j]:
                continue
            if _jaccard(tokens[i], tokens[j]) >= threshold:
                union(i, j)

    # Pass 4: assemble clusters.
    clusters: dict[int, dict] = {}
    for idx, (summary, count) in enumerate(items):
        root = find(idx)
        cluster = clusters.setdefault(
            root,
            {"canonical_summary": summary, "total_count": 0, "session_count": 0, "variants": []},
        )
        cluster["total_count"] += count
        cluster["session_count"] += 1  # one extra distinct summary in this cluster
        cluster["variants"].append({"summary": summary, "count": count})
        # canonical = highest-count variant in the cluster
        if count > cluster["variants"][0]["count"]:
            cluster["canonical_summary"] = summary

    out = list(clusters.values())
    for c in out:
        # session_count: number of distinct exact-summary rows folded in.
        # total_count gives us total activities; we already track this above.
        c["variants"] = sorted(c["variants"], key=lambda v: -v["count"])
    out.sort(key=lambda c: -c["total_count"])
    return out


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


async def _session_policy() -> SessionPolicy:
    cfg = await asyncio.get_event_loop().run_in_executor(None, load_config)
    return SessionPolicy(
        capture_interval_seconds=cfg.capture_interval_seconds,
        gap_split_seconds=max(180, 3 * cfg.capture_interval_seconds),
    )


async def _blocks_for_range(conn, lo: str, hi: str, policy: SessionPolicy) -> list[Block]:
    """Sessionize the range's samples (incl. unclassified screen time)."""
    samples = await fetch_samples(conn, lo, hi)
    range_end = min(
        datetime.fromisoformat(hi),
        datetime.now(UTC).replace(tzinfo=None),
    )
    return sessionize(samples, policy, range_end=range_end)


def _state_seconds(blocks: list[Block]) -> dict[str, float]:
    """Apportion each block's duration to states by their sample share."""
    out: dict[str, float] = defaultdict(float)
    for b in blocks:
        for state, share in b.state_shares.items():
            out[state] += b.duration_seconds * share
    return out


async def _query_confidence(conn, lo: str, hi: str) -> dict[str, float | None]:
    cur = await conn.execute(
        """SELECT task_category, AVG(task_category_confidence)
           FROM activities
           WHERE started_at >= ? AND started_at <= ?
           GROUP BY task_category""",
        (lo, hi),
    )
    return {r[0]: r[1] for r in await cur.fetchall()}


def _category_buckets(
    blocks: list[Block], observed: int, confidence: dict[str, float | None]
) -> list[dict]:
    totals = compute_totals(blocks)
    counts: Counter = Counter()
    for b in blocks:
        counts[b.task_category or "other"] += b.sample_count
    return sorted(
        (
            {
                "task_category": cat,
                "count": counts[cat],
                "avg_confidence": confidence.get(cat),
                "seconds": secs,
                "pct": _pct(secs, observed),
            }
            for cat, secs in totals["by_category"].items()
        ),
        key=lambda c: -c["seconds"],
    )


def _state_buckets(blocks: list[Block], observed: int) -> list[dict]:
    counts: Counter = Counter()
    for b in blocks:
        for s in b.state_shares:
            counts[s] += round(b.sample_count * b.state_shares[s])
    return sorted(
        (
            {
                "productivity_state": state,
                "count": counts[state],
                "seconds": int(secs),
                "pct": _pct(secs, observed),
            }
            for state, secs in _state_seconds(blocks).items()
        ),
        key=lambda s: -s["seconds"],
    )


def _app_buckets(blocks: list[Block], observed: int, limit: int = 10) -> list[dict]:
    totals = compute_totals(blocks)
    counts: Counter = Counter()
    for b in blocks:
        counts[b.app_name or "unknown"] += b.sample_count
    buckets = sorted(
        (
            {
                "app_name": app,
                "count": counts[app],
                "seconds": secs,
                "pct": _pct(secs, observed),
            }
            for app, secs in totals["by_app"].items()
        ),
        key=lambda a: -a["seconds"],
    )
    return buckets[:limit]


def _heatmap_from_blocks(blocks: list[Block], observed: int) -> list[dict]:
    """Apportion block time to local hour-of-day cells across the whole range."""
    hour_seconds = [0.0] * 24
    hour_state: list[dict[str, float]] = [defaultdict(float) for _ in range(24)]

    for b in blocks:
        # Stored timestamps are naive UTC; heatmap hours are the user's local hours.
        cursor = b.start.replace(tzinfo=UTC).astimezone()
        end = b.end.replace(tzinfo=UTC).astimezone()
        while cursor < end:
            next_hour = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            seg_end = min(end, next_hour)
            seg = (seg_end - cursor).total_seconds()
            hour_seconds[cursor.hour] += seg
            for state, share in b.state_shares.items():
                hour_state[cursor.hour][state] += seg * share
            cursor = seg_end

    cells = []
    for h in range(24):
        by_state = hour_state[h]
        dominant_state = max(by_state.items(), key=lambda kv: kv[1])[0] if by_state else None
        cells.append(
            {
                "hour": h,
                "pct": _pct(hour_seconds[h], observed),
                "dominant_state": dominant_state,
                "by_state_pct": {s: _pct(v, observed) for s, v in by_state.items()},
            }
        )
    return cells


def _state_pcts_from_blocks(blocks: list[Block], observed: int) -> dict[str, float]:
    """Share of observed time that was classified / productive / distracted."""
    classified = sum(
        b.duration_seconds for b in blocks if b.task_category != UNCLASSIFIED
    )
    state_secs = _state_seconds(blocks)
    prod = sum(state_secs.get(s, 0.0) for s in PRODUCTIVE_STATES)
    distr = sum(state_secs.get(s, 0.0) for s in DISTRACTED_STATES)
    return {
        "active_pct": _pct(classified, observed),
        "productive_pct": _pct(prod, observed),
        "distracted_pct": _pct(distr, observed),
    }


async def _query_total_captures(conn, lo: str, hi: str) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM captures WHERE captured_at >= ? AND captured_at <= ?",
        (lo, hi),
    )
    row = await cur.fetchone()
    return int(row[0]) if row else 0


async def _query_recurring(
    conn, lo: str, hi: str, total: int, *, top_n: int = 5
) -> list[dict]:
    cur = await conn.execute(
        """SELECT summary, COUNT(*) as count
           FROM activities
           WHERE started_at >= ? AND started_at <= ?
             AND summary IS NOT NULL AND TRIM(summary) <> ''
           GROUP BY summary""",
        (lo, hi),
    )
    rows = await cur.fetchall()
    clusters = _cluster_summaries([(r[0], r[1]) for r in rows])
    out = []
    for c in clusters[:top_n]:
        out.append(
            {
                "canonical_summary": c["canonical_summary"],
                "pct": _pct(c["total_count"], total),
                "session_count": c["total_count"],
                "variant_count": len(c["variants"]),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/insights/daily")
async def daily_insights(date: str = Query(...)):
    """Legacy single-day endpoint — used by StatsBar.

    Kept for back-compat. Returns counts only; new code should use
    /insights/summary instead.
    """
    lo, hi = _day_bounds(date)
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """SELECT task_category, COUNT(*) as count,
               AVG(task_category_confidence) as avg_confidence
               FROM activities WHERE started_at >= ? AND started_at <= ?
               GROUP BY task_category ORDER BY count DESC""",
            (lo, hi),
        )
        categories = [
            {"task_category": r[0], "count": r[1], "avg_confidence": r[2]}
            for r in await cur.fetchall()
        ]
        cur = await conn.execute(
            """SELECT productivity_state, COUNT(*) as count
               FROM activities WHERE started_at >= ? AND started_at <= ?
               GROUP BY productivity_state ORDER BY count DESC""",
            (lo, hi),
        )
        states = [
            {"productivity_state": r[0], "count": r[1]}
            for r in await cur.fetchall()
        ]
        cur = await conn.execute(
            """SELECT
                 COALESCE(a.app_name_override, c.app_name) AS effective_app,
                 COUNT(*) AS count
               FROM captures c
               LEFT JOIN activities a ON a.capture_id = c.id
               WHERE c.captured_at >= ? AND c.captured_at <= ?
                 AND c.app_name IS NOT NULL
               GROUP BY effective_app
               ORDER BY count DESC
               LIMIT 10""",
            (lo, hi),
        )
        top_apps = [{"app_name": r[0], "count": r[1]} for r in await cur.fetchall()]
    return {
        "date": date,
        "categories": categories,
        "productivity_states": states,
        "top_apps": top_apps,
    }


@router.get("/insights/summary")
async def insights_summary(
    date: str = Query(..., description="YYYY-MM-DD anchor (right edge of the range)"),
    period: str = Query("day", description="day | week | month"),
):
    """Unified insights endpoint scoped by period.

    period="day"   → exactly `date`
    period="week"  → 7 days ending on `date`
    period="month" → 30 days ending on `date`

    Time metrics are expressed as percentage of observed block-time in the
    period (interval union over session blocks — see sessions.py), so an hour
    with two busy monitors counts once. `count` fields remain sample counts.
    """
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="period must be day|week|month")

    lo, hi, span = _period_range(date, period)
    base_lo, base_hi, _n_periods, base_label = _baseline_range(date, period)
    policy = await _session_policy()

    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        total = await _query_total_captures(conn, lo, hi)

        blocks = await _blocks_for_range(conn, lo, hi, policy)
        observed = compute_totals(blocks)["observed_seconds"]
        confidence = await _query_confidence(conn, lo, hi)

        categories = _category_buckets(blocks, observed, confidence)
        states = _state_buckets(blocks, observed)
        top_apps = _app_buckets(blocks, observed)
        heatmap = _heatmap_from_blocks(blocks, observed)
        current = _state_pcts_from_blocks(blocks, observed)

        # Baseline pcts are normalized to the baseline's own observed time, so
        # "vs 7-day average" compares like with like even on sparse weeks.
        base_blocks = await _blocks_for_range(conn, base_lo, base_hi, policy)
        base_observed = compute_totals(base_blocks)["observed_seconds"]
        baseline_raw = _state_pcts_from_blocks(base_blocks, base_observed)

        recurring = await _query_recurring(conn, lo, hi, total)

    comparison = {
        "baseline_label": base_label,
        "active": {
            "current_pct": current["active_pct"],
            "baseline_pct": baseline_raw["active_pct"],
        },
        "productive": {
            "current_pct": current["productive_pct"],
            "baseline_pct": baseline_raw["productive_pct"],
        },
        "distracted": {
            "current_pct": current["distracted_pct"],
            "baseline_pct": baseline_raw["distracted_pct"],
        },
    }

    return {
        "period": period,
        "date": date,
        "range": {"start": lo, "end": hi, "span_days": span},
        "total_captures": total,
        "observed_seconds": observed,
        "categories": categories,
        "productivity_states": states,
        "top_apps": top_apps,
        "hourly_heatmap": heatmap,
        "comparison": comparison,
        "recurring_activities": recurring,
    }


@router.get("/insights/weekly")
async def weekly_insights(week_start: str = Query(..., description="YYYY-MM-DD of Monday")):
    # 7 local days starting on week_start; group by LOCAL day.
    end_date = (_parse_date(week_start) + timedelta(days=6)).strftime("%Y-%m-%d")
    lo, hi = local_range_bounds_utc(end_date, 7)
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """SELECT date(started_at, 'localtime') as day, task_category, COUNT(*) as count
               FROM activities
               WHERE started_at >= ? AND started_at <= ?
               GROUP BY day, task_category ORDER BY day""",
            (lo, hi),
        )
        rows = await cur.fetchall()
    return {
        "week_start": week_start,
        "data": [
            {"day": r[0], "task_category": r[1], "count": r[2]} for r in rows
        ],
    }
