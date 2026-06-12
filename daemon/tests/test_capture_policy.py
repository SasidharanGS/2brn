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


# ── adaptive tick pacing ─────────────────────────────────────────────────────


def test_tick_backs_off_exponentially_while_idle():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)  # change → 1s
    assert policy.next_tick_seconds(0.0) == 1.0
    policy.select([_frame()], [HASH_NEAR], now=1.0)
    assert policy.next_tick_seconds(1.0) == 2.0
    policy.select([_frame()], [HASH_NEAR], now=3.0)
    assert policy.next_tick_seconds(3.0) == 4.0
    policy.select([_frame()], [HASH_NEAR], now=7.0)
    assert policy.next_tick_seconds(7.0) == 8.0


def test_tick_backoff_caps_at_max_idle():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    for i in range(10):
        policy.select([_frame()], [HASH_NEAR], now=1.0 + i)
    assert policy.next_tick_seconds(11.0) == 16.0


def test_change_snaps_tick_back_to_min():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    for i in range(5):
        policy.select([_frame()], [HASH_NEAR], now=1.0 + i)
    assert policy.next_tick_seconds(5.0) > 1.0
    policy.select([_frame()], [HASH_FAR], now=6.0)
    assert policy.next_tick_seconds(6.0) == 1.0


def test_cooldown_suppressed_change_still_resets_tick():
    """A suppressed change means the screen is active — keep sampling fast so
    the post-cooldown keep lands promptly."""
    policy = _policy(change_cooldown_seconds=60.0)
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    policy.select([_frame()], [HASH_NEAR], now=1.0)
    policy.select([_frame()], [HASH_NEAR], now=3.0)
    assert policy.next_tick_seconds(3.0) == 4.0
    assert policy.select([_frame()], [HASH_FAR], now=4.0) == []  # suppressed
    assert policy.next_tick_seconds(4.0) == 1.0


def test_idle_backoff_grows_on_empty_ticks_too():
    """All-excluded ticks are idle ticks: nothing observed, nothing changing."""
    policy = _policy()
    policy.select([], [], now=0.0)
    assert policy.next_tick_seconds(0.0) == 2.0


def test_sleep_never_overshoots_the_next_heartbeat():
    policy = _policy()
    policy.select([_frame()], [HASH_ZERO], now=100.0)  # heartbeat tick
    for i in range(6):
        policy.select([_frame()], [HASH_NEAR], now=101.0 + i)
    # Backed off to 16s, but the next heartbeat is due at t=160.
    assert policy.next_tick_seconds(150.0) == 10.0


def test_sleep_is_at_least_min_tick_even_when_heartbeat_overdue():
    policy = _policy()
    assert policy.next_tick_seconds(1000.0) == 1.0


def test_max_idle_tick_ceiling_is_configurable():
    policy = _policy(max_idle_tick_seconds=4.0)
    policy.select([_frame()], [HASH_ZERO], now=0.0)
    for i in range(5):
        policy.select([_frame()], [HASH_NEAR], now=1.0 + i)
    assert policy.next_tick_seconds(5.0) == 4.0
