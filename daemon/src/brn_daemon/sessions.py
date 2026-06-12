"""Sessionizer: fold the per-capture activity sample stream into duration blocks.

The activities table stores point-in-time *samples* — one observation per kept
capture (~one per heartbeat interval, plus screen changes). A *block* is a
contiguous run of samples on one monitor with the same app and task category,
with no gap larger than the split threshold. Durations are a property of
blocks, not samples.

Blocks are derived on read and never stored: the grouping rules are policy,
and deriving means a policy change is a code change, not a data migration.
User category overrides, purges, and backfills reflow automatically.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SessionPolicy:
    """Tunable grouping rules. Defaults follow the 60s capture heartbeat.

    A gap longer than ``gap_split_seconds`` ends a block: the user was away,
    paused, in an excluded app, or the screen had no readable text. Three
    heartbeats tolerates a single missed/sparse capture without splitting.
    """

    capture_interval_seconds: int = 60
    gap_split_seconds: int = 180


@dataclass
class Block:
    start: datetime
    end: datetime
    monitor_index: int
    app_name: str | None
    task_category: str | None
    dominant_state: str | None
    sample_count: int
    summary: str | None

    @property
    def duration_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.removesuffix("Z"))


def _run_to_block(run: list[dict], end: datetime) -> Block:
    states = Counter(s["productivity_state"] for s in run if s.get("productivity_state"))
    summary = next((s["summary"] for s in reversed(run) if s.get("summary")), None)
    return Block(
        start=run[0]["_ts"],
        end=end,
        monitor_index=int(run[0].get("monitor_index") or 0),
        app_name=run[0].get("app_name"),
        task_category=run[0].get("task_category"),
        dominant_state=states.most_common(1)[0][0] if states else None,
        sample_count=len(run),
        summary=summary,
    )


def sessionize(
    samples: list[dict],
    policy: SessionPolicy | None = None,
    range_end: datetime | None = None,
) -> list[Block]:
    """Group activity samples into duration blocks, one lane per monitor.

    Each sample dict needs ``started_at`` plus optional ``app_name``,
    ``task_category``, ``productivity_state``, ``summary``, ``monitor_index``.

    A new block starts when the app changes, the task category changes, or the
    gap since the previous sample exceeds the split threshold. A block ends one
    capture interval after its last sample — that's the window the observation
    vouches for — clamped to the next block's start on the same lane and to
    ``range_end`` (so today's last block never extends into the future).
    """
    policy = policy or SessionPolicy()
    tail = timedelta(seconds=policy.capture_interval_seconds)
    gap_split = timedelta(seconds=policy.gap_split_seconds)

    lanes: dict[int, list[dict]] = {}
    for s in samples:
        s = {**s, "_ts": _parse_ts(s["started_at"])}
        lanes.setdefault(int(s.get("monitor_index") or 0), []).append(s)

    blocks: list[Block] = []
    for lane in lanes.values():
        lane.sort(key=lambda s: s["_ts"])

        runs: list[list[dict]] = []
        for s in lane:
            prev = runs[-1][-1] if runs else None
            if (
                prev is None
                or s.get("app_name") != prev.get("app_name")
                or s.get("task_category") != prev.get("task_category")
                or s["_ts"] - prev["_ts"] > gap_split
            ):
                runs.append([s])
            else:
                runs[-1].append(s)

        for i, run in enumerate(runs):
            end = run[-1]["_ts"] + tail
            if i + 1 < len(runs):
                end = min(end, runs[i + 1][0]["_ts"])
            if range_end is not None:
                end = min(end, range_end)
            end = max(end, run[-1]["_ts"])  # never end before the last observation
            blocks.append(_run_to_block(run, end))

    blocks.sort(key=lambda b: (b.start, b.monitor_index))
    return blocks


def _union_seconds(intervals: list[tuple[datetime, datetime]]) -> int:
    """Total seconds covered by the union of intervals (overlaps counted once)."""
    if not intervals:
        return 0
    intervals = sorted(intervals)
    total = 0.0
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start > cur_end:
            total += (cur_end - cur_start).total_seconds()
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    total += (cur_end - cur_start).total_seconds()
    return int(total)


def compute_totals(blocks: list[Block]) -> dict:
    """Clock-time totals via interval union.

    ``observed_seconds`` is wall-clock time with any block active — an hour
    with two busy monitors counts once. Per-category/app figures are each that
    key's own union, so concurrent monitors may legitimately overlap across
    categories while no single figure exceeds wall-clock time.
    """
    by_category: dict[str, list[tuple[datetime, datetime]]] = {}
    by_app: dict[str, list[tuple[datetime, datetime]]] = {}
    for b in blocks:
        by_category.setdefault(b.task_category or "other", []).append((b.start, b.end))
        by_app.setdefault(b.app_name or "unknown", []).append((b.start, b.end))
    return {
        "observed_seconds": _union_seconds([(b.start, b.end) for b in blocks]),
        "by_category": {k: _union_seconds(v) for k, v in by_category.items()},
        "by_app": {k: _union_seconds(v) for k, v in by_app.items()},
    }
