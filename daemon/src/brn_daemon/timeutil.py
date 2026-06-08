"""Timezone helpers for day-bucketing.

Timestamps are stored in SQLite as naive UTC ISO strings (``%Y-%m-%dT%H:%M:%S.%f``,
no offset). For journals, blogs, insights, and date-filtered chat, "a day" means
the user's *local* calendar day — a personal journal for "June 8" should cover
the user's local June 8, not a UTC window offset by hours.

These helpers convert between the stored UTC strings and local-day boundaries so
day-bucketing is correct in every timezone, not only UTC. Bounds are returned in
the same naive-UTC format the timestamps are stored in, so they can be compared
directly (``started_at >= ? AND started_at <= ?``) and still use the index.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

DB_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def utc_now_iso() -> str:
    """Current time as a naive-UTC DB timestamp string (no offset)."""
    return datetime.now(UTC).strftime(DB_TS_FMT)


def _parse_utc(ts: str) -> datetime:
    """Parse a stored timestamp as an aware UTC datetime.

    Stored values are naive UTC; we tolerate a trailing ``Z``/offset and a
    missing microsecond component for robustness against older rows.
    """
    raw = ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def utc_iso_to_local_date(ts: str | None) -> str:
    """Return the user's local calendar date (YYYY-MM-DD) for a stored UTC ts."""
    if not ts:
        return ""
    return _parse_utc(ts).astimezone().strftime("%Y-%m-%d")


def local_range_bounds_utc(end_date: str, span_days: int = 1) -> tuple[str, str]:
    """Naive-UTC ``(start, end)`` bounds for ``span_days`` local days ending on
    (and including) the local calendar date ``end_date`` (YYYY-MM-DD).

    ``span_days=1`` → just that local day. ``end`` is the last microsecond of the
    final local day. A naive local wall-clock time converted with ``astimezone``
    is interpreted in the system's local timezone (the user's, on the desktop).
    """
    end_d = datetime.strptime(end_date, "%Y-%m-%d")
    start_local = (end_d - timedelta(days=span_days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_local = end_d.replace(hour=23, minute=59, second=59, microsecond=999999)
    start_utc = start_local.astimezone(UTC).strftime(DB_TS_FMT)
    end_utc = end_local.astimezone(UTC).strftime(DB_TS_FMT)
    return start_utc, end_utc


def local_day_bounds_utc(date_str: str) -> tuple[str, str]:
    """Naive-UTC ``(start, end)`` bounds covering the single local day ``date_str``."""
    return local_range_bounds_utc(date_str, span_days=1)
