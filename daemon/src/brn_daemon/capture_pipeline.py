"""The capture pipeline's per-frame work: OCR reuse and the classification
routing, plus the per-monitor memo caches they depend on.

Extracted from ``main.py`` so this stateful logic — *which* classification
source a kept frame is routed to, and the OCR-reuse decision — has a dedicated,
unit-testable home, the way :class:`~brn_daemon.capture_policy.CapturePolicy`
owns the keep/skip decision. ``main._capture_loop`` is then just orchestration:
``select → save → ocr → record``.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from brn_daemon.capture import save_screenshot
from brn_daemon.capture_policy import KeptFrame
from brn_daemon.inference import InferenceQueue, clone_activity
from brn_daemon.ocr import extract_text, is_text_sparse
from brn_daemon.timeutil import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorMemo:
    """The last freshly-OCR'd capture per monitor — what unchanged heartbeats reuse."""

    capture_id: int
    ocr_text: str


@dataclass(frozen=True)
class SparseMemo:
    """The last metadata-classified sparse capture per monitor.

    Metadata-only classification depends only on (app_name, window_title), so
    while those stay the same, later sparse frames clone this capture's
    activity instead of re-running inference — a video would otherwise pay an
    LLM call for the same classification on every change keep.
    """

    app_name: str
    window_title: str
    capture_id: int


def save_screenshot_off_loop(
    loop: asyncio.AbstractEventLoop,
    img,
    *,
    key: bytes | None,
    monitor_index: int = 0,
):
    """Schedule save_screenshot (JPEG encode + optional AES + disk write) in the executor."""
    def save_screenshot_bound():
        return save_screenshot(img, key=key, monitor_index=monitor_index)
    save_screenshot_bound.__name__ = "save_screenshot"
    return loop.run_in_executor(None, save_screenshot_bound)


class CaptureRecorder:
    """Owns the per-monitor OCR/sparse memo caches and routes each kept frame to
    its cheapest classification source.

    One instance lives for the life of the capture loop. ``ocr_memos`` and
    ``sparse_memos`` are public so they can be seeded/inspected in tests.
    """

    def __init__(self) -> None:
        self.ocr_memos: dict[int, MonitorMemo] = {}
        self.sparse_memos: dict[int, SparseMemo] = {}

    async def ocr_kept_frames(
        self,
        loop: asyncio.AbstractEventLoop,
        kept: list[KeptFrame],
    ) -> list[tuple[str, bool]]:
        """OCR the kept frames, reusing memoised text for unchanged heartbeat frames.

        Returns one ``(ocr_text, reused)`` pair per frame, in order. An unchanged
        frame is pixel-similar to the monitor's previous kept frame, so rerunning
        tesseract could only re-derive the text we already have.
        """
        def reusable(item: KeptFrame) -> bool:
            return item.unchanged and item.frame.monitor_index in self.ocr_memos

        fresh = [(i, item) for i, item in enumerate(kept) if not reusable(item)]
        fresh_texts = await asyncio.gather(*[
            loop.run_in_executor(None, extract_text, item.frame.image) for _, item in fresh
        ])
        texts: dict[int, str] = {i: text for (i, _), text in zip(fresh, fresh_texts)}
        return [
            (texts[i], False) if i in texts else (self.ocr_memos[item.frame.monitor_index].ocr_text, True)
            for i, item in enumerate(kept)
        ]

    async def record(
        self,
        conn,
        inference_queue: InferenceQueue,
        item: KeptFrame,
        file_path,
        ocr_text: str,
        reused: bool,
    ) -> None:
        """Insert one kept frame's capture row and route it to a classification source.

        Cheapest source first:
        - unchanged heartbeat → clone the memoised fresh capture's activity
          (``reused`` implies the monitor has an entry in ``ocr_memos``)
        - readable OCR text → normal inference
        - sparse text with app/window metadata → metadata-only inference; while
          the metadata stays the same, later sparse frames clone the result
        - nothing to go on → record the capture, leave it unclassified
        """
        frame = item.frame
        now_iso = utc_now_iso()
        cur = await conn.execute(
            "INSERT INTO captures (captured_at, app_name, window_title, file_path, "
            "ocr_text, phash, trigger, monitor_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now_iso, frame.app_name, frame.window_title, str(file_path),
             ocr_text, item.phash, item.trigger, frame.monitor_index)
        )
        await conn.commit()
        capture_id: int = cur.lastrowid  # type: ignore[assignment]

        if reused:
            cloned = await clone_activity(
                conn,
                source_capture_id=self.ocr_memos[frame.monitor_index].capture_id,
                capture_id=capture_id,
                started_at=now_iso,
            )
            if cloned:
                logger.info(
                    "Capture #%d → unchanged heartbeat — reused OCR + classification",
                    capture_id,
                )
                return
            # Source has no activity yet (inference pending, failed, or sparse) —
            # fall through to the normal routing with the reused text, but keep the
            # memo pointing at the original root so later heartbeats can still
            # clone its activity once it lands.
        else:
            self.ocr_memos[frame.monitor_index] = MonitorMemo(
                capture_id=capture_id, ocr_text=ocr_text
            )

        if not is_text_sparse(ocr_text):
            await inference_queue.enqueue(
                capture_id, frame.app_name, frame.window_title, ocr_text, now_iso
            )
            logger.info("Capture #%d → inference queued", capture_id)
            return

        if frame.app_name or frame.window_title:
            memo = self.sparse_memos.get(frame.monitor_index)
            if (
                memo is not None
                and (memo.app_name, memo.window_title) == (frame.app_name, frame.window_title)
                and await clone_activity(
                    conn, source_capture_id=memo.capture_id,
                    capture_id=capture_id, started_at=now_iso,
                )
            ):
                logger.info("Capture #%d → sparse text — cloned metadata classification", capture_id)
                return
            # New metadata (or the memoised classification never landed): infer from
            # app + window title, and make this capture the monitor's new sparse root.
            await inference_queue.enqueue(
                capture_id, frame.app_name, frame.window_title, ocr_text, now_iso
            )
            self.sparse_memos[frame.monitor_index] = SparseMemo(
                app_name=frame.app_name, window_title=frame.window_title, capture_id=capture_id
            )
            logger.info("Capture #%d → sparse text — metadata-only inference queued", capture_id)
            return

        logger.info("Capture #%d → saved (no readable text or metadata, skipping inference)", capture_id)
