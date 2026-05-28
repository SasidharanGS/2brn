"""Async event bus for daemon-internal pub/sub.

Used by the plugin orchestrator to listen for triggers (journal_generated, etc.)
fired by other daemon subsystems. Out-of-process subscribers (UI) get events via
SSE / polling, not this bus.

Payload contract (per event):
    journal_generated:  {"date": "YYYY-MM-DD", "content": str}
    blog_generated:     {"date": "YYYY-MM-DD", "content": str}
    capture_inferred:   {"summary": str, "task_category": str, "app_name": str,
                         "timestamp": iso8601, "tags": list[str]}
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventNames:
    JOURNAL_GENERATED = "journal_generated"
    BLOG_GENERATED = "blog_generated"
    CAPTURE_INFERRED = "capture_inferred"

    ALL = (JOURNAL_GENERATED, BLOG_GENERATED, CAPTURE_INFERRED)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subs.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        if event_name in self._subs:
            try:
                self._subs[event_name].remove(handler)
            except ValueError:
                pass

    async def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        """Fire an event. Handler exceptions are logged but do not stop other handlers."""
        handlers = list(self._subs.get(event_name, ()))
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._safe_call(h, event_name, payload) for h in handlers),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.exception("Event handler raised: %s", r)

    @staticmethod
    async def _safe_call(handler: Handler, event_name: str, payload: dict[str, Any]) -> None:
        try:
            await handler(event_name, payload)
        except Exception:
            logger.exception("Handler for event %s failed", event_name)
