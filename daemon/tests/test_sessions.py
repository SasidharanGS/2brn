"""Tests for the sessionizer (sessions.py) and GET /sessions."""

from datetime import datetime, timedelta

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from brn_daemon.db import get_db_path, init_db
from brn_daemon.sessions import Block, SessionPolicy, compute_totals, sessionize
from brn_daemon.timeutil import local_day_bounds_utc

T0 = datetime(2026, 5, 28, 10, 0, 0)
POLICY = SessionPolicy(capture_interval_seconds=60, gap_split_seconds=180)


def sample(
    offset_seconds: int,
    app: str = "Code",
    category: str = "work",
    state: str = "focused",
    summary: str | None = "coding",
    monitor: int = 1,
) -> dict:
    return {
        "started_at": (T0 + timedelta(seconds=offset_seconds)).isoformat(),
        "app_name": app,
        "task_category": category,
        "productivity_state": state,
        "summary": summary,
        "monitor_index": monitor,
    }


# ── pure sessionize ─────────────────────────────────────────────────────────


def test_empty_input_yields_no_blocks():
    assert sessionize([], POLICY) == []


def test_single_sample_block_lasts_one_interval():
    [b] = sessionize([sample(0)], POLICY)
    assert b.start == T0
    assert b.end == T0 + timedelta(seconds=60)
    assert b.duration_seconds == 60
    assert b.sample_count == 1


def test_consecutive_same_app_and_category_merge():
    [b] = sessionize([sample(0), sample(60), sample(120)], POLICY)
    assert b.sample_count == 3
    assert b.duration_seconds == 180  # last sample + one interval


def test_app_change_splits_and_clamps_previous_end():
    blocks = sessionize([sample(0), sample(30, app="Safari")], POLICY)
    assert len(blocks) == 2
    # First block's tail (60s) is clamped to the next block's start (30s).
    assert blocks[0].end == T0 + timedelta(seconds=30)
    assert blocks[1].app_name == "Safari"


def test_category_change_splits_within_same_app():
    blocks = sessionize(
        [sample(0, app="Safari"), sample(60, app="Safari", category="play")], POLICY
    )
    assert len(blocks) == 2
    assert [b.task_category for b in blocks] == ["work", "play"]


def test_state_change_does_not_split_and_dominant_state_wins():
    [b] = sessionize(
        [
            sample(0, state="focused"),
            sample(60, state="distracted"),
            sample(120, state="focused"),
        ],
        POLICY,
    )
    assert b.sample_count == 3
    assert b.dominant_state == "focused"


def test_gap_below_threshold_does_not_split():
    [b] = sessionize([sample(0), sample(120)], POLICY)  # 120s < 180s
    assert b.sample_count == 2


def test_gap_above_threshold_splits():
    blocks = sessionize([sample(0), sample(240)], POLICY)  # 240s > 180s
    assert len(blocks) == 2
    assert blocks[0].end == T0 + timedelta(seconds=60)  # tail, not the gap


def test_monitors_form_independent_lanes():
    blocks = sessionize(
        [sample(0, monitor=1), sample(0, monitor=2, app="Slack", category="communication")],
        POLICY,
    )
    assert len(blocks) == 2
    assert {b.monitor_index for b in blocks} == {1, 2}


def test_range_end_clamps_block_tail():
    range_end = T0 + timedelta(seconds=30)
    [b] = sessionize([sample(0)], POLICY, range_end=range_end)
    assert b.end == range_end


def test_block_never_ends_before_last_observation():
    # range_end before the sample itself must not produce a negative block
    [b] = sessionize([sample(0)], POLICY, range_end=T0 - timedelta(seconds=10))
    assert b.end == b.start
    assert b.duration_seconds == 0


def test_summary_is_most_recent_non_empty():
    [b] = sessionize(
        [sample(0, summary="first"), sample(60, summary="latest"), sample(120, summary=None)],
        POLICY,
    )
    assert b.summary == "latest"


def test_z_suffixed_timestamps_are_accepted():
    [b] = sessionize([{**sample(0), "started_at": T0.isoformat() + "Z"}], POLICY)
    assert b.start == T0


# ── totals (interval union) ─────────────────────────────────────────────────


def _block(start_s: int, end_s: int, category: str = "work", app: str = "Code") -> Block:
    return Block(
        start=T0 + timedelta(seconds=start_s),
        end=T0 + timedelta(seconds=end_s),
        monitor_index=1,
        app_name=app,
        task_category=category,
        dominant_state="focused",
        sample_count=1,
        summary=None,
    )


def test_totals_count_overlapping_monitors_once():
    # Two monitors active over the same hour: observed time is one hour.
    blocks = [_block(0, 3600), _block(0, 3600, category="communication", app="Slack")]
    totals = compute_totals(blocks)
    assert totals["observed_seconds"] == 3600
    assert totals["by_category"] == {"work": 3600, "communication": 3600}
    assert totals["by_app"] == {"Code": 3600, "Slack": 3600}


def test_totals_sum_disjoint_blocks():
    totals = compute_totals([_block(0, 60), _block(600, 720)])
    assert totals["observed_seconds"] == 180
    assert totals["by_category"]["work"] == 180


def test_totals_empty():
    assert compute_totals([]) == {
        "observed_seconds": 0,
        "by_category": {},
        "by_app": {},
    }


# ── GET /sessions route ─────────────────────────────────────────────────────


@pytest.fixture
async def sessions_client(tmp_home):
    from brn_daemon.main import create_app

    await init_db()
    lo, _hi = local_day_bounds_utc("2026-05-28")
    base = datetime.fromisoformat(lo) + timedelta(hours=10)

    async with aiosqlite.connect(get_db_path()) as conn:
        for i, (offset, app) in enumerate(
            [(0, "Code"), (60, "Code"), (120, "Safari")], start=1
        ):
            ts = (base + timedelta(seconds=offset)).isoformat()
            await conn.execute(
                "INSERT INTO captures (id, captured_at, app_name, trigger, monitor_index) "
                "VALUES (?, ?, ?, 'heartbeat', 1)",
                (i, ts, app),
            )
            await conn.execute(
                "INSERT INTO activities (capture_id, started_at, summary, task_category, "
                "task_category_confidence, productivity_state, productivity_confidence) "
                "VALUES (?, ?, 'doing things', 'work', 0.9, 'focused', 0.9)",
                (i, ts),
            )
        await conn.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_sessions_route_groups_by_app(sessions_client):
    resp = await sessions_client.get("/sessions?date=2026-05-28")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-05-28"
    assert len(data["blocks"]) == 2  # Code (2 samples) | Safari (1 sample)
    code, safari = data["blocks"]
    assert code["app_name"] == "Code"
    assert code["sample_count"] == 2
    assert safari["app_name"] == "Safari"
    assert code["start"].endswith("Z") and code["end"].endswith("Z")
    assert data["totals"]["observed_seconds"] > 0
    assert "work" in data["totals"]["by_category"]


async def test_sessions_route_rejects_malformed_date(sessions_client):
    resp = await sessions_client.get("/sessions?date=not-a-date")
    assert resp.status_code == 400


async def test_sessions_route_empty_day(sessions_client):
    resp = await sessions_client.get("/sessions?date=2026-05-29")
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocks"] == []
    assert data["totals"]["observed_seconds"] == 0
