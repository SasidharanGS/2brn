"""Tests for the insights endpoints — focus on /insights/summary.

Exercises the period/range math, hour-of-day heatmap, baseline comparison,
and recurring-activity clustering. Uses a FastAPI TestClient against a
locally-seeded SQLite DB.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brn_daemon.db import get_db_path, init_db
from brn_daemon.routes.insights_routes import _cluster_summaries
from brn_daemon.routes.insights_routes import router as insights_router

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_capture_and_activity(
    cur: sqlite3.Cursor,
    *,
    started_at: str,
    app_name: str = "Chrome",
    summary: str = "writing code",
    state: str = "productive",
    category: str = "work",
) -> None:
    cur.execute(
        "INSERT INTO captures (captured_at, app_name, trigger) VALUES (?, ?, 'heartbeat')",
        (started_at, app_name),
    )
    capture_id = cur.lastrowid
    cur.execute(
        """INSERT INTO activities
             (capture_id, started_at, summary, task_category,
              task_category_confidence, productivity_state, productivity_confidence)
           VALUES (?, ?, ?, ?, 0.9, ?, 0.8)""",
        (capture_id, started_at, summary, category, state),
    )


@pytest.fixture
async def seeded_client(tmp_home):
    """FastAPI TestClient with a small synthetic DB.

    Anchor date = 2026-05-23. Seeds:
      - today (2026-05-23): 5 productive activities at 09:00, 09:01, 09:02
        on Chrome; 2 distracted at 14:00 on Twitter.
      - yesterday (2026-05-22): 3 productive at 10:00 on Chrome.
      - last week (2026-05-16): 1 distracted at 21:00 on Twitter.
      - one cluster of 3 near-duplicate summaries today.
    """
    await init_db()

    today = "2026-05-23"
    yesterday = "2026-05-22"
    last_week = "2026-05-16"

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()

        # Today — morning productive block on Chrome (5 activities, 09:00–09:04)
        for i in range(5):
            _seed_capture_and_activity(
                cur,
                started_at=f"{today}T09:0{i}:00",
                app_name="Chrome",
                summary="reviewing pull request comments on GitHub",
                state="productive",
                category="work",
            )
        # Today — afternoon distraction (2 activities, 14:00 + 14:01)
        for i in range(2):
            _seed_capture_and_activity(
                cur,
                started_at=f"{today}T14:0{i}:00",
                app_name="Twitter",
                summary="scrolling Twitter feed",
                state="distracted",
                category="play",
            )
        # Today — 3 near-duplicate recurring activity summaries.
        # These intentionally share most tokens with the 09:* block so the
        # Jaccard clustering can merge them at the default threshold (0.6).
        _seed_capture_and_activity(
            cur, started_at=f"{today}T10:00:00",
            summary="reviewing pull request comments on GitHub channel",
            state="productive", category="work",
        )
        _seed_capture_and_activity(
            cur, started_at=f"{today}T10:01:00",
            summary="reviewing pull request feedback comments on GitHub",
            state="productive", category="work",
        )
        _seed_capture_and_activity(
            cur, started_at=f"{today}T10:02:00",
            summary="reviewing pull request review comments on GitHub",
            state="productive", category="work",
        )

        # Yesterday — 3 productive activities (baseline)
        for i in range(3):
            _seed_capture_and_activity(
                cur,
                started_at=f"{yesterday}T10:0{i}:00",
                state="productive", category="work",
            )

        # Last week — late-night distraction (1)
        _seed_capture_and_activity(
            cur,
            started_at=f"{last_week}T21:00:00",
            state="distracted", category="play",
        )

        conn.commit()

    app = FastAPI()
    app.include_router(insights_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# /insights/summary — happy path
# ---------------------------------------------------------------------------


def test_summary_day_returns_required_shape(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    assert r.status_code == 200
    data = r.json()

    assert data["period"] == "day"
    assert data["date"] == "2026-05-23"
    assert data["range"]["span_days"] == 1
    assert "categories" in data
    assert "productivity_states" in data
    assert "top_apps" in data
    assert "hourly_heatmap" in data
    assert "comparison" in data
    assert "recurring_activities" in data
    assert len(data["hourly_heatmap"]) == 24


def test_summary_day_categories_use_block_time(seeded_client):
    """pct is share of observed block-time, not of capture counts.

    Like its fixture-sharing neighbours, assumes TZ=UTC (the CI contract) —
    the seeded 14:00 UTC rows fall on the next local day in far-east zones.
    """
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    data = r.json()
    cats = data["categories"]
    assert cats, "expected at least one category bucket"
    observed = data["observed_seconds"]
    # Blocks: work 09:00–09:05 (300s) + work 10:00–10:03 (180s) + play 14:00–14:02 (120s)
    assert observed == 600
    for c in cats:
        assert "task_category" in c
        assert "count" in c
        assert "seconds" in c
        assert c["pct"] == round(c["seconds"] / observed * 100, 1)
    by_cat = {c["task_category"]: c for c in cats}
    assert by_cat["work"]["seconds"] == 480
    assert by_cat["work"]["pct"] == 80.0
    assert by_cat["play"]["seconds"] == 120
    assert by_cat["work"]["count"] == 8  # counts stay sample counts


def test_summary_pct_is_time_based_not_count_based(tmp_home):
    """Three rapid-fire work samples ≠ 3× the time of one play sample.

    Seeds change-triggered work samples 5s apart (their blocks clamp to the
    next sample) so count-share (75%) and time-share diverge — pinning that
    the switch to block-time actually changed the semantics.
    """
    import asyncio as _asyncio
    from datetime import timedelta

    from brn_daemon.timeutil import local_day_bounds_utc

    async def _seed():
        await init_db()

    _asyncio.run(_seed())

    day = "2026-05-23"
    base = datetime.fromisoformat(local_day_bounds_utc(day)[0]) + timedelta(hours=12)
    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.cursor()
        # Work: 3 samples 5s apart → block of 10s + 60s tail = 70s
        for offset in (0, 5, 10):
            _seed_capture_and_activity(
                cur, started_at=(base + timedelta(seconds=offset)).isoformat(),
                app_name="Code", summary="coding", state="focused", category="work",
            )
        # Play: 1 sample much later → its own 60s block
        _seed_capture_and_activity(
            cur, started_at=(base + timedelta(minutes=30)).isoformat(),
            app_name="Steam", summary="gaming", state="chilling", category="play",
        )
        conn.commit()

    app = FastAPI()
    app.include_router(insights_router)
    client = TestClient(app)

    data = client.get(f"/insights/summary?period=day&date={day}").json()
    by_cat = {c["task_category"]: c for c in data["categories"]}
    assert data["observed_seconds"] == 130
    assert by_cat["work"]["seconds"] == 70
    assert by_cat["work"]["pct"] == round(70 / 130 * 100, 1)   # 53.8 — NOT 75.0
    assert by_cat["play"]["seconds"] == 60
    assert by_cat["work"]["count"] == 3


def test_summary_includes_unclassified_screen_time(tmp_home):
    """A capture with no activity row surfaces as unclassified time and
    lowers active_pct below 100."""
    import asyncio as _asyncio
    from datetime import timedelta

    from brn_daemon.timeutil import local_day_bounds_utc

    async def _seed():
        await init_db()

    _asyncio.run(_seed())

    day = "2026-05-23"
    base = datetime.fromisoformat(local_day_bounds_utc(day)[0]) + timedelta(hours=9)
    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.cursor()
        _seed_capture_and_activity(
            cur, started_at=base.isoformat(),
            app_name="Code", summary="coding", state="focused", category="work",
        )
        # Activity-less capture (sparse text, e.g. video) 10 min later
        cur.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, trigger) "
            "VALUES (?, 'VLC', 'movie.mkv', 'heartbeat')",
            ((base + timedelta(minutes=10)).isoformat(),),
        )
        conn.commit()

    app = FastAPI()
    app.include_router(insights_router)
    client = TestClient(app)

    data = client.get(f"/insights/summary?period=day&date={day}").json()
    by_cat = {c["task_category"]: c for c in data["categories"]}
    assert "unclassified" in by_cat
    assert by_cat["unclassified"]["seconds"] == 60
    assert by_cat["unclassified"]["avg_confidence"] is None
    # 60s work + 60s unclassified observed → only half the time is classified
    assert data["comparison"]["active"]["current_pct"] == 50.0


def test_summary_day_top_apps_includes_chrome_and_twitter(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    apps = {a["app_name"]: a for a in r.json()["top_apps"]}
    assert "Chrome" in apps
    assert "Twitter" in apps
    assert apps["Chrome"]["count"] > apps["Twitter"]["count"]


def test_summary_day_heatmap_dominant_state_at_morning_hours(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    heatmap = {cell["hour"]: cell for cell in r.json()["hourly_heatmap"]}

    local_offset = datetime.now(UTC).astimezone().utcoffset()

    def utc_to_local_hour(utc_h: int) -> int:
        dt = datetime(2026, 5, 23, utc_h, 0, 0, tzinfo=UTC)
        return (dt + local_offset).hour

    prod_hour = utc_to_local_hour(9)
    dist_hour = utc_to_local_hour(14)

    # Productive block seeded at UTC 09:* → local prod_hour
    assert heatmap[prod_hour]["dominant_state"] == "productive", (
        f"Expected hour {prod_hour} to be productive, got: {heatmap[prod_hour]}"
    )
    assert heatmap[prod_hour]["pct"] > 0

    # Distracted seeded at UTC 14:* → local dist_hour
    assert heatmap[dist_hour]["dominant_state"] == "distracted", (
        f"Expected hour {dist_hour} to be distracted, got: {heatmap[dist_hour]}"
    )

    # UTC 03:* → some local hour that had no activities (guard: only check if no overlap)
    empty_hour = utc_to_local_hour(3)
    if empty_hour not in (prod_hour, dist_hour):
        assert heatmap[empty_hour]["pct"] == 0
        assert heatmap[empty_hour]["dominant_state"] is None


def test_summary_day_comparison_baseline_label(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    comp = r.json()["comparison"]
    assert comp["baseline_label"] == "7-day average"
    assert "current_pct" in comp["active"]
    assert "baseline_pct" in comp["active"]


def test_summary_day_comparison_active_pct_today(seeded_client):
    """Today seeded with 10 activities out of 10 captures → 100% active."""
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    comp = r.json()["comparison"]
    assert comp["active"]["current_pct"] == 100.0
    assert comp["productive"]["current_pct"] == 80.0
    assert comp["distracted"]["current_pct"] == 20.0


def test_summary_day_baseline_averaged_over_7_days(seeded_client):
    """Yesterday had 3 captures in the baseline window. per_period_total = 3 // 7 = 0
    so baseline_pct resolves to 0 (safe division guard).
    """
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    comp = r.json()["comparison"]
    assert "baseline_pct" in comp["productive"]


def test_summary_recurring_clusters_near_duplicates(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=2026-05-23")
    recurring = r.json()["recurring_activities"]
    assert recurring, "expected at least one recurring cluster"
    top = recurring[0]
    # The top cluster should fold the 5 'reviewing pull request comments…'
    # rows plus the 3 near-duplicates (8 total).
    assert top["session_count"] >= 6
    assert top["variant_count"] >= 2
    assert "github" in top["canonical_summary"].lower() or "pr" in top["canonical_summary"].lower()


def test_summary_week_period_widens_range(seeded_client):
    r = seeded_client.get("/insights/summary?period=week&date=2026-05-23")
    data = r.json()
    assert data["period"] == "week"
    assert data["range"]["span_days"] == 7
    # Range includes today (10 captures) + yesterday (3 captures) = 13 total
    comp = data["comparison"]
    assert comp["active"]["current_pct"] == 100.0
    assert comp["baseline_label"] == "4-week average"


def test_summary_month_period_baseline_label(seeded_client):
    r = seeded_client.get("/insights/summary?period=month&date=2026-05-23")
    data = r.json()
    assert data["period"] == "month"
    assert data["range"]["span_days"] == 30
    assert data["comparison"]["baseline_label"] == "3-month average"


# ---------------------------------------------------------------------------
# /insights/summary — error paths
# ---------------------------------------------------------------------------


def test_summary_rejects_unknown_period(seeded_client):
    r = seeded_client.get("/insights/summary?period=year&date=2026-05-23")
    assert r.status_code == 400


def test_summary_rejects_malformed_date(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=not-a-date")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /insights/daily — back-compat
# ---------------------------------------------------------------------------


def test_legacy_daily_endpoint_still_returns_counts(seeded_client):
    r = seeded_client.get("/insights/daily?date=2026-05-23")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert "productivity_states" in data
    assert "top_apps" in data
    # Legacy endpoint must not include total_minutes (back-compat contract).
    assert all("total_minutes" not in c for c in data["categories"])


# ---------------------------------------------------------------------------
# _cluster_summaries — unit tests
# ---------------------------------------------------------------------------


def test_cluster_summaries_groups_near_duplicates():
    rows = [
        ("reviewing pull request comments on GitHub", 5),
        ("reading PR review feedback on GitHub", 1),
        ("looking at PR comments on GitHub", 1),
        ("scrolling Twitter feed", 4),
        ("reading documentation about FastAPI", 2),
    ]
    clusters = _cluster_summaries(rows, threshold=0.3)
    assert len(clusters) >= 2  # GitHub group, Twitter group, docs group
    # The largest cluster should be the GitHub PR-comments family.
    top = clusters[0]
    assert top["total_count"] >= 5
    assert len(top["variants"]) >= 2


def test_cluster_summaries_keeps_distinct_when_no_overlap():
    rows = [
        ("walking the dog", 1),
        ("brewing coffee", 1),
        ("playing chess", 1),
    ]
    clusters = _cluster_summaries(rows, threshold=0.6)
    assert len(clusters) == 3


def test_cluster_summaries_empty_input():
    assert _cluster_summaries([]) == []


def test_cluster_summaries_canonical_is_highest_count():
    rows = [
        ("scrolling Twitter feed", 1),
        ("scrolling Twitter posts feed", 10),
    ]
    clusters = _cluster_summaries(rows, threshold=0.3)
    assert len(clusters) == 1
    assert clusters[0]["canonical_summary"] == "scrolling Twitter posts feed"
