"""Tests for local-day timezone bucketing (review finding F-CORE-3).

These pin TZ explicitly (via time.tzset) so they are deterministic regardless of
the machine/CI timezone — that is exactly the class of bug being fixed.
"""
import os
import time

import pytest

from brn_daemon.timeutil import (
    local_day_bounds_utc,
    local_range_bounds_utc,
    utc_iso_to_local_date,
    utc_now_iso,
)


@pytest.fixture
def tz_kolkata():
    """Run under Asia/Kolkata (UTC+5:30) to exercise non-UTC bucketing."""
    prev = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Kolkata"
    time.tzset()
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = prev
        time.tzset()


def test_utc_now_iso_is_naive_no_offset():
    s = utc_now_iso()
    assert "+" not in s and not s.endswith("Z")
    assert "T" in s


def test_local_day_bounds_in_kolkata(tz_kolkata):
    # Local 2026-06-08 in IST (UTC+5:30) spans UTC 06-07 18:30 .. 06-08 18:29:59.999999
    lo, hi = local_day_bounds_utc("2026-06-08")
    assert lo == "2026-06-07T18:30:00.000000"
    assert hi == "2026-06-08T18:29:59.999999"


def test_utc_ts_maps_to_correct_local_date_in_kolkata(tz_kolkata):
    # 2026-06-07 20:00 UTC = 2026-06-08 01:30 IST → local date is the 8th
    assert utc_iso_to_local_date("2026-06-07T20:00:00.000000") == "2026-06-08"
    # 2026-06-08 17:00 UTC = 2026-06-08 22:30 IST → still the 8th
    assert utc_iso_to_local_date("2026-06-08T17:00:00.000000") == "2026-06-08"
    # 2026-06-08 19:00 UTC = 2026-06-09 00:30 IST → rolls to the 9th
    assert utc_iso_to_local_date("2026-06-08T19:00:00.000000") == "2026-06-09"


def test_local_range_bounds_spans_days(tz_kolkata):
    lo, hi = local_range_bounds_utc("2026-06-08", span_days=7)
    # 7 local days ending 06-08 → starts local 06-02 00:00 = UTC 06-01 18:30
    assert lo == "2026-06-01T18:30:00.000000"
    assert hi == "2026-06-08T18:29:59.999999"


def test_utc_iso_to_local_date_handles_empty():
    assert utc_iso_to_local_date("") == ""
    assert utc_iso_to_local_date(None) == ""


def test_bounds_under_utc_match_plain_calendar_day():
    prev = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        lo, hi = local_day_bounds_utc("2026-06-08")
        assert lo == "2026-06-08T00:00:00.000000"
        assert hi == "2026-06-08T23:59:59.999999"
    finally:
        if prev is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = prev
        time.tzset()
