"""CapturePolicy: per-tick keep/skip decisions.

Hashes are synthetic hex strings (is_duplicate works on hamming distance), so
every test is deterministic and independent of image content. 64-bit hashes at
threshold 0.95 tolerate at most 3 differing bits.
"""
from PIL import Image

from brn_daemon.capture_policy import CapturePolicy, Frame

_IMG = Image.new("RGB", (8, 8), color=0)

HASH_ZERO = "0" * 16          # baseline
HASH_NEAR = "0" * 15 + "1"    # 1 bit off  → similarity 63/64 ≈ 0.98 → duplicate
HASH_FAR = "f" * 16           # 64 bits off → similarity 0      → change


def _frame(monitor_idx: int = 1) -> Frame:
    return Frame(
        monitor_index=monitor_idx,
        image=_IMG,
        monitor_rect={"left": 0, "top": 0},
        app_name="Code",
        window_title="window",
    )


def _policy(**overrides) -> CapturePolicy:
    kwargs = {"heartbeat_seconds": 60.0, "change_cooldown_seconds": 5.0, **overrides}
    return CapturePolicy(**kwargs)


def _bits(n: int) -> str:
    """A 64-bit hash with the n lowest bits set — n hamming steps from HASH_ZERO."""
    return f"{(1 << n) - 1:016x}"


# ── change trigger ───────────────────────────────────────────────────────────


def test_first_frame_ever_is_kept_as_change():
    kept = _policy().select([_frame()], [HASH_ZERO], now=0.0)
    assert len(kept) == 1
    assert kept[0].trigger == "change"
    assert kept[0].unchanged is False


def test_unchanged_frame_is_skipped():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    assert policy.select([_frame()], [HASH_NEAR], now=10.0) == []


def test_changed_frame_is_kept_with_change_trigger():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    kept = policy.select([_frame()], [HASH_FAR], now=10.0)
    assert len(kept) == 1
    assert kept[0].trigger == "change"
    assert kept[0].phash == HASH_FAR


def test_skipped_frames_do_not_become_the_baseline():
    """Slow drift must accumulate against the last *kept* frame until it trips.

    One extra bit per tick: each frame is a duplicate of its predecessor, so a
    baseline that followed every frame would never fire. Against the fixed
    kept-frame baseline, the 4th bit crosses the 0.95 threshold.
    """
    policy = _policy(change_cooldown_seconds=0.0)
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    for tick, n in enumerate((1, 2, 3), start=1):
        assert policy.select([_frame()], [_bits(n)], now=float(tick)) == []
    kept = policy.select([_frame()], [_bits(4)], now=4.0)
    assert len(kept) == 1
    assert kept[0].trigger == "change"


# ── change cooldown ──────────────────────────────────────────────────────────


def test_changes_within_cooldown_are_suppressed():
    policy = _policy(change_cooldown_seconds=5.0)
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    assert policy.select([_frame()], [HASH_FAR], now=1.0) == []
    assert policy.select([_frame()], [HASH_FAR], now=4.9) == []


def test_change_is_kept_once_cooldown_expires():
    policy = _policy(change_cooldown_seconds=5.0)
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    policy.select([_frame()], [HASH_FAR], now=1.0)  # suppressed
    kept = policy.select([_frame()], [HASH_FAR], now=5.0)
    assert len(kept) == 1
    assert kept[0].trigger == "change"


def test_cooldown_is_per_monitor():
    policy = _policy(change_cooldown_seconds=5.0)
    policy.select([_frame(1)], [HASH_ZERO], now=0.0)
    kept = policy.select([_frame(2)], [HASH_ZERO], now=1.0)
    assert [k.frame.monitor_index for k in kept] == [2]


def test_heartbeat_is_not_blocked_by_cooldown():
    policy = _policy(change_cooldown_seconds=120.0)
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    assert policy.select([_frame()], [HASH_FAR], now=30.0) == []  # cooldown
    kept = policy.select([_frame()], [HASH_FAR], now=60.0)
    assert len(kept) == 1
    assert kept[0].trigger == "heartbeat"
    assert kept[0].unchanged is False


# ── heartbeat trigger ────────────────────────────────────────────────────────


def test_heartbeat_keeps_unchanged_frames_and_flags_them():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    kept = policy.select([_frame()], [HASH_NEAR], now=60.0)
    assert len(kept) == 1
    assert kept[0].trigger == "heartbeat"
    assert kept[0].unchanged is True


def test_no_heartbeat_before_the_interval_elapses():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    assert policy.select([_frame()], [HASH_NEAR], now=59.0) == []


def test_heartbeat_clock_resets_even_when_no_frames_survive_exclusion():
    """A heartbeat tick with everything excluded still counts as the heartbeat."""
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=100.0)  # first tick: heartbeat
    policy.select([], [], now=161.0)                   # heartbeat tick, all excluded
    # 9s after the empty heartbeat: not a heartbeat, unchanged → skipped
    assert policy.select([_frame()], [HASH_NEAR], now=170.0) == []


def test_multi_monitor_selection_is_independent():
    policy = _policy()
    policy.select([_frame(1), _frame(2)], [HASH_ZERO, HASH_ZERO], now=0.0)
    kept = policy.select([_frame(1), _frame(2)], [HASH_NEAR, HASH_FAR], now=10.0)
    assert [k.frame.monitor_index for k in kept] == [2]
