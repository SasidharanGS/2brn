"""Per-tick keep/skip policy for the capture loop.

The capture pipeline has three cost tiers: grabbing + hashing every frame
(paid every tick), JPEG encode + OCR per kept frame, and LLM inference per
kept frame with readable text. This module owns the decision of which frames
are worth pushing into the expensive tiers. Two triggers keep a frame:

- ``change``: the frame's perceptual hash drifted below the similarity
  threshold vs the last *kept* frame on that monitor. Skipped frames never
  become the comparison baseline, so slow drift accumulates until it trips
  the threshold. Change keeps are rate-limited per monitor — a video or
  animation otherwise trips the trigger on every tick and pays JPEG + OCR +
  inference at tick rate.
- ``heartbeat``: every ``heartbeat_seconds``, every monitor's frame is kept
  even if unchanged, so the capture timeline never has gaps longer than the
  heartbeat. Sessions and insights rely on that bound when deriving duration
  blocks from the sample stream.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

from brn_daemon.dedup import is_duplicate

SIMILARITY_THRESHOLD = 0.95

# At most one change-triggered keep per monitor per cooldown window. Suppressed
# changes are not lost: the baseline stays put, so the accumulated difference
# triggers a keep as soon as the window expires (or the next heartbeat lands).
CHANGE_COOLDOWN_SECONDS = 5.0


@dataclass(frozen=True)
class Frame:
    """One monitor's grab for the current tick."""

    monitor_index: int
    image: Image.Image
    monitor_rect: dict
    app_name: str
    window_title: str


@dataclass(frozen=True)
class KeptFrame:
    """A frame that survived the keep policy, plus why it was kept.

    ``unchanged`` is True for heartbeat keeps that are pixel-similar to the
    previous kept frame on that monitor — downstream stages can skip work
    whose output cannot differ from last time (change keeps are never
    unchanged by construction).
    """

    frame: Frame
    trigger: str  # "change" | "heartbeat"
    phash: str
    unchanged: bool


class CapturePolicy:
    """Stateful keep/skip decisions, one ``select()`` call per tick.

    All methods take ``now`` (a monotonic timestamp) instead of reading a
    clock, so the policy is deterministic under test.
    """

    def __init__(
        self,
        *,
        heartbeat_seconds: float,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        change_cooldown_seconds: float = CHANGE_COOLDOWN_SECONDS,
    ) -> None:
        self._heartbeat_seconds = heartbeat_seconds
        self._similarity_threshold = similarity_threshold
        self._change_cooldown_seconds = change_cooldown_seconds
        self._baseline_phashes: dict[int, str] = {}  # monitor → phash of last kept frame
        self._last_change_at: dict[int, float] = {}  # monitor → time of last changed keep
        self._last_heartbeat = 0.0

    def select(self, frames: Sequence[Frame], phashes: Sequence[str], now: float) -> list[KeptFrame]:
        """Apply the keep policy to one tick's frames.

        Resets the heartbeat clock whenever a heartbeat tick happens, even if
        every frame was excluded upstream — the heartbeat is "an attempt to
        keep everything", not "something was kept".
        """
        is_heartbeat = (now - self._last_heartbeat) >= self._heartbeat_seconds
        if is_heartbeat:
            self._last_heartbeat = now

        kept: list[KeptFrame] = []
        for frame, phash in zip(frames, phashes, strict=True):
            baseline = self._baseline_phashes.get(frame.monitor_index)
            unchanged = is_duplicate(phash, baseline, threshold=self._similarity_threshold)
            if not is_heartbeat:
                if unchanged or self._in_change_cooldown(frame.monitor_index, now):
                    continue
            self._baseline_phashes[frame.monitor_index] = phash
            if not unchanged:
                self._last_change_at[frame.monitor_index] = now
            kept.append(KeptFrame(
                frame=frame,
                trigger="heartbeat" if is_heartbeat else "change",
                phash=phash,
                unchanged=unchanged,
            ))
        return kept

    def _in_change_cooldown(self, monitor_index: int, now: float) -> bool:
        last_change = self._last_change_at.get(monitor_index)
        return last_change is not None and (now - last_change) < self._change_cooldown_seconds
