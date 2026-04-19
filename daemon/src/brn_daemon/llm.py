import asyncio
import logging
from collections.abc import AsyncIterator

import litellm

litellm.drop_params = True  # silently drop unsupported params per provider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3

_PROVIDER_PREFIX = {
    "openai_compatible": "openai",
    "openai": "openai",
    "anthropic": "anthropic",
    "azure": "azure",
    "ollama": "ollama",
    "groq": "groq",
    "together": "together_ai",
    "cohere": "cohere",
}


def make_chat_kwargs(
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict,
) -> dict:
    """Build kwargs dict for litellm.acompletion()."""
    prefix = _PROVIDER_PREFIX.get(provider_type, "openai")
    kwargs: dict = {
        "model": f"{prefix}/{model}",
        "api_key": api_key or "no-key",
    }
    if base_url:
        kwargs["base_url"] = base_url
    if extra_headers:
        kwargs["extra_headers"] = extra_headers
    return kwargs


async def chat_complete(
    messages: list[dict],
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict,
) -> str:
    kwargs = make_chat_kwargs(provider_type, base_url, api_key, model, extra_headers)
    kwargs["messages"] = messages
    kwargs["stream"] = False

    for attempt in range(_MAX_RETRIES):
        try:
            resp = await litellm.acompletion(**kwargs)
            if resp is None or not resp.choices:  # type: ignore[union-attr]
                raise ValueError("Provider returned empty response (check base_url and model name)")
            return resp.choices[0].message.content or ""  # type: ignore[union-attr]
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("Chat attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError("Unreachable")


async def chat_stream(
    messages: list[dict],
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict,
) -> AsyncIterator[str]:
    kwargs = make_chat_kwargs(provider_type, base_url, api_key, model, extra_headers)
    kwargs["messages"] = messages
    kwargs["stream"] = True

    try:
        resp = await litellm.acompletion(**kwargs)
        if resp is None:
            logger.error("Chat stream failed: provider returned None (check base_url and model name)")
            yield "Error: provider returned empty response"
            return
    except Exception as exc:
        logger.error("Chat stream failed: %s", exc)
        yield f"Error: {exc}"
        return
    async for chunk in resp:  # type: ignore[union-attr]
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def make_chat_fn():
    """Return (chat_complete_fn, stream_fn) bound to current config."""
    from brn_daemon.config import get_chat_api_key, load_config
    cfg = load_config()
    cp = cfg.chat_provider
    api_key = get_chat_api_key() or ""

    async def _complete(messages: list[dict]) -> str:
        return await chat_complete(
            messages=messages,
            provider_type=cp.type,
            base_url=cp.base_url,
            api_key=api_key,
            model=cp.model,
            extra_headers=cp.extra_headers,
        )

    async def _stream(messages: list[dict]) -> AsyncIterator[str]:
        async for chunk in chat_stream(
            messages=messages,
            provider_type=cp.type,
            base_url=cp.base_url,
            api_key=api_key,
            model=cp.model,
            extra_headers=cp.extra_headers,
        ):
            yield chunk

    return _complete, _stream
