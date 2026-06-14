"""Application context — a typed container for the daemon's long-lived services
and mutable runtime state.

This replaces the former global ``app_state`` ``TypedDict`` dict that routes
reached into via late ``from brn_daemon.main import app_state`` imports. The
context is created once per app (in ``create_app``) and its service fields are
populated during ``lifespan``. Route handlers receive it through
``Depends(get_context)``; background tasks (the capture loop, scheduler jobs,
the AI-client rebuild) are handed it explicitly.

The payoff: routers no longer import from ``main`` (the circular edge is gone),
and every field is typed instead of an ``Any`` from ``dict.get``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from brn_daemon.blog import BlogGenerator
    from brn_daemon.chat import ChatService
    from brn_daemon.embeddings import ChromaStore
    from brn_daemon.inference import InferenceQueue
    from brn_daemon.journal import JournalGenerator
    from brn_daemon.plugins import EventBus, PluginOrchestrator


@dataclass
class AppContext:
    """Per-app singletons + mutable runtime state. One instance lives on
    ``app.state.context`` for the life of the process."""

    # ── Mutable runtime state ──────────────────────────────────────────────
    paused: bool = False
    capture_count_today: int = 0
    last_captured_at: str | None = None
    # Set True to force the capture loop to refresh its app-exclusion cache on
    # the next tick (instead of waiting out the 30s TTL).
    exclusions_dirty: bool = True
    screenshot_key: bytes | None = None
    api_token: str | None = None
    # Dates with an in-flight journal/blog generation — guards against
    # concurrent duplicate generation for the same day.
    journal_generating: set[str] = field(default_factory=set)
    blog_generating: set[str] = field(default_factory=set)

    # ── Long-lived services (populated during lifespan) ────────────────────
    journal_generator: JournalGenerator | None = None
    blog_generator: BlogGenerator | None = None
    chat_service: ChatService | None = None
    chroma_store: ChromaStore | None = None
    event_bus: EventBus | None = None
    plugin_orchestrator: PluginOrchestrator | None = None
    scheduler: AsyncIOScheduler | None = None
    inference_queue: InferenceQueue | None = None
    embed_client: object | None = None
    vault_watcher: object | None = None


def get_context(request: Request) -> AppContext:
    """FastAPI dependency: the per-app :class:`AppContext` on ``app.state``."""
    return request.app.state.context
