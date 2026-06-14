"""Construction and hot-swap of the AI-backed services on an :class:`AppContext`.

Lives outside ``main`` so the settings route can trigger a provider rebuild
without importing the composition root (which would reintroduce the circular
edge the context refactor removed).
"""
from __future__ import annotations

import logging

from brn_daemon.chat import ChatService
from brn_daemon.context import AppContext
from brn_daemon.embeddings import EmbeddingService
from brn_daemon.llm import make_chat_fn
from brn_daemon.providers import make_embed_client

logger = logging.getLogger(__name__)


async def rebuild_ai_clients(ctx: AppContext) -> None:
    """Rebuild chat and embed clients from the current config and push them into
    every in-memory consumer, without restarting the daemon.

    Called after ``PUT /settings`` saves provider changes.
    """
    old_embed = ctx.embed_client
    new_chat_fn, new_stream_fn = make_chat_fn()
    new_embed_client = make_embed_client()

    if old_embed is not None:
        try:
            await old_embed.aclose()  # type: ignore[union-attr]
        except Exception:
            logger.exception("Error closing old embed client during rebuild")

    chroma = ctx.chroma_store
    new_embedding_service = EmbeddingService(embed_client=new_embed_client, chroma_store=chroma)
    new_chat_service = ChatService(
        chat_fn=new_chat_fn,
        stream_fn=new_stream_fn,
        embed_client=new_embed_client,
        chroma_store=chroma,
    )

    ctx.chat_service = new_chat_service
    ctx.embed_client = new_embed_client

    if ctx.inference_queue is not None:
        ctx.inference_queue.set_chat_fn(new_chat_fn)
        ctx.inference_queue.set_embedding_service(new_embedding_service)
    if ctx.journal_generator is not None:
        ctx.journal_generator.set_chat_fn(new_chat_fn)
    if ctx.blog_generator is not None:
        ctx.blog_generator.set_chat_fn(new_chat_fn)
    if ctx.plugin_orchestrator is not None:
        ctx.plugin_orchestrator.chat_fn = new_chat_fn

    logger.info("AI clients rebuilt from updated config")
