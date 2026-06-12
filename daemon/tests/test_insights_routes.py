"""Tests for /insights/summary — block-time metrics, ranges, heatmap, baseline.

All seeded timestamps are derived from local_day_bounds_utc so the suite
passes in ANY timezone: "local midnight UTC-instant + 9h" is local 09:00
wherever the tests run, which is exactly how the endpoints bucket time.
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brn_daemon.db import get_db_path, init_db
from brn_daemon.routes.insights_routes import _cluster_summaries
from brn_daemon.routes.insights_routes import router as insights_router
from brn_daemon.timeutil import local_day_bounds_utc

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TODAY = "2026-05-23"
YESTERDAY = "2026-05-22"
LAST_WEEK = "2026-05-16"


def _local(day: str, hours: float, seconds: int = 0) -> str:
    """Naive-UTC timestamp for local wall-clock `hours` on local day `day`."""
    lo, _hi = local_day_bounds_utc(day)
    return (
        datetime.fromisoformat(lo) + timedelta(hours=hours, seconds=seconds)
    ).isoformat()


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


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(insights_router)
    return TestClient(app)


@pytest.fixture
def seeded_client(tmp_home):
    """TestClient over a small synthetic DB (timezone-independent seeding).

    Local-time blocks on TODAY:
      09:00–09:05  work / productive / Chrome   (5 samples, 300s)
      10:00–10:03  work / productive / Chrome   (3 near-duplicate summaries, 180s)
      14:00–14:02  play / distracted / Twitter  (2 samples, 120s)
    → observed 600s: work 480s (80%), play 120s (20%)

    Baseline: YESTERDAY 3 productive work samples (one 180s block);
    LAST_WEEK one late-night distracted sample.
    """
    asyncio.run(init_db())

    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.cursor()

        for i in range(5):
            _seed_capture_and_activity(
                cur, started_at=_local(TODAY, 9, i * 60),
                summary="reviewing pull request comments on GitHub",
            )
        for i, summary in enumerate([
            "reviewing pull request comments on GitHub channel",
            "reviewing pull request feedback comments on GitHub",
            "reviewing pull request review comments on GitHub",
        ]):
            _seed_capture_and_activity(
                cur, started_at=_local(TODAY, 10, i * 60), summary=summary,
            )
        for i in range(2):
            _seed_capture_and_activity(
                cur, started_at=_local(TODAY, 14, i * 60),
                app_name="Twitter", summary="scrolling Twitter feed",
                state="distracted", category="play",
            )

        for i in range(3):
            _seed_capture_and_activity(
                cur, started_at=_local(YESTERDAY, 10, i * 60),
            )

        _seed_capture_and_activity(
            cur, started_at=_local(LAST_WEEK, 21),
            app_name="Twitter", state="distracted", category="play",
        )

        conn.commit()

    return _client()


# ---------------------------------------------------------------------------
# /insights/summary — happy path
# ---------------------------------------------------------------------------


def test_summary_day_returns_required_shape(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    assert r.status_code == 200
    data = r.json()

    assert data["period"] == "day"
    assert data["date"] == TODAY
    assert data["range"]["span_days"] == 1
    assert "observed_seconds" in data
    assert "categories" in data
    assert "productivity_states" in data
    assert "top_apps" in data
    assert "hourly_heatmap" in data
    assert "comparison" in data
    assert "recurring_activities" in data
    assert len(data["hourly_heatmap"]) == 24


def test_summary_day_categories_are_block_time_shares(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    data = r.json()
    assert data["observed_seconds"] == 600
    by_cat = {c["task_category"]: c for c in data["categories"]}
    assert by_cat["work"]["seconds"] == 480
    assert by_cat["work"]["pct"] == 80.0
    assert by_cat["play"]["seconds"] == 120
    assert by_cat["play"]["pct"] == 20.0
    for c in data["categories"]:
        assert c["pct"] == round(c["seconds"] / data["observed_seconds"] * 100, 1)


def test_summary_day_states_are_time_apportioned(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    by_state = {s["productivity_state"]: s for s in r.json()["productivity_states"]}
    assert by_state["productive"]["seconds"] == 480
    assert by_state["distracted"]["seconds"] == 120


def test_summary_day_top_apps_ranked_by_time(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    apps = {a["app_name"]: a for a in r.json()["top_apps"]}
    assert apps["Chrome"]["seconds"] == 480
    assert apps["Twitter"]["seconds"] == 120
    assert r.json()["top_apps"][0]["app_name"] == "Chrome"


def test_summary_day_heatmap_lands_on_local_hours(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    heatmap = {cell["hour"]: cell for cell in r.json()["hourly_heatmap"]}

    assert heatmap[9]["dominant_state"] == "productive"
    assert heatmap[9]["pct"] == 50.0  # 300s of 600s observed
    assert heatmap[10]["dominant_state"] == "productive"
    assert heatmap[14]["dominant_state"] == "distracted"
    assert heatmap[3]["pct"] == 0
    assert heatmap[3]["dominant_state"] is None


def test_summary_day_comparison_is_time_based(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    comp = r.json()["comparison"]
    assert comp["baseline_label"] == "7-day average"
    assert comp["active"]["current_pct"] == 100.0
    assert comp["productive"]["current_pct"] == 80.0
    assert comp["distracted"]["current_pct"] == 20.0
    # Baseline (7 days ending yesterday) = yesterday's 180s productive block +
    # last week's 60s distracted block → 180/240 of its own observed time.
    assert comp["productive"]["baseline_pct"] == 75.0
    assert comp["distracted"]["baseline_pct"] == 25.0


def test_summary_pct_is_time_based_not_count_based(tmp_home):
    """Three rapid-fire work samples ≠ 3× the time of one play sample.

    Change-triggered samples 5s apart clamp to the next sample, so
    count-share (75%) and time-share (53.8%) diverge.
    """
    asyncio.run(init_db())
    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.cursor()
        for offset in (0, 5, 10):
            _seed_capture_and_activity(
                cur, started_at=_local(TODAY, 12, offset),
                app_name="Code", summary="coding", state="focused", category="work",
            )
        _seed_capture_and_activity(
            cur, started_at=_local(TODAY, 12.5),
            app_name="Steam", summary="gaming", state="chilling", category="play",
        )
        conn.commit()

    data = _client().get(f"/insights/summary?period=day&date={TODAY}").json()
    by_cat = {c["task_category"]: c for c in data["categories"]}
    assert data["observed_seconds"] == 130
    assert by_cat["work"]["seconds"] == 70  # 10s span + 60s tail
    assert by_cat["work"]["pct"] == round(70 / 130 * 100, 1)  # 53.8 — NOT 75.0
    assert by_cat["play"]["seconds"] == 60


def test_summary_includes_unclassified_screen_time(tmp_home):
    """A capture with no activity row surfaces as unclassified time and
    lowers active_pct below 100."""
    asyncio.run(init_db())
    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.cursor()
        _seed_capture_and_activity(
            cur, started_at=_local(TODAY, 9),
            app_name="Code", summary="coding", state="focused", category="work",
        )
        cur.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, trigger) "
            "VALUES (?, 'VLC', 'movie.mkv', 'heartbeat')",
            (_local(TODAY, 9, 600),),
        )
        conn.commit()

    data = _client().get(f"/insights/summary?period=day&date={TODAY}").json()
    by_cat = {c["task_category"]: c for c in data["categories"]}
    assert by_cat["unclassified"]["seconds"] == 60
    # 60s work + 60s unclassified observed → only half the time is classified
    assert data["comparison"]["active"]["current_pct"] == 50.0


def test_summary_recurring_clusters_with_approx_time(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=day&date={TODAY}")
    recurring = r.json()["recurring_activities"]
    assert recurring, "expected at least one recurring cluster"
    top = recurring[0]
    # Folds the 5 'reviewing pull request comments…' rows + 3 near-duplicates.
    assert top["occurrences"] == 8
    assert top["approx_seconds"] == 8 * 60  # one capture interval per occurrence
    assert top["variant_count"] >= 2
    assert "github" in top["canonical_summary"].lower()


def test_summary_week_period_widens_range(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=week&date={TODAY}")
    data = r.json()
    assert data["period"] == "week"
    assert data["range"]["span_days"] == 7
    # Today's 600s + yesterday's 180s block
    assert data["observed_seconds"] == 780
    assert data["comparison"]["active"]["current_pct"] == 100.0
    assert data["comparison"]["baseline_label"] == "4-week average"


def test_summary_month_period_baseline_label(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=month&date={TODAY}")
    data = r.json()
    assert data["period"] == "month"
    assert data["range"]["span_days"] == 30
    assert data["comparison"]["baseline_label"] == "3-month average"


def test_summary_empty_day_is_all_zeroes(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=2026-01-01")
    data = r.json()
    assert data["observed_seconds"] == 0
    assert data["categories"] == []
    assert data["comparison"]["active"]["current_pct"] == 0.0


# ---------------------------------------------------------------------------
# /insights/summary — error paths
# ---------------------------------------------------------------------------


def test_summary_rejects_unknown_period(seeded_client):
    r = seeded_client.get(f"/insights/summary?period=year&date={TODAY}")
    assert r.status_code == 400


def test_summary_rejects_malformed_date(seeded_client):
    r = seeded_client.get("/insights/summary?period=day&date=not-a-date")
    assert r.status_code == 400


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
    assert len(clusters) >= 2
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
