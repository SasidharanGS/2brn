import asyncio
import logging
from typing import Protocol, runtime_checkable

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


@runtime_checkable
class EmbedClient(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class JLLEmbedClient:
    """Embed client for JLL Gateway's custom format.

    Request:  POST /v1/embeddings  {"model": "...", "inputs": ["text1", ...]}
    Response: {"success": true, "data": {"embeddings": [[...], ...]}}
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._http = httpx.AsyncClient(
            timeout=30,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._http.post(
                    f"{self._base_url}/v1/embeddings",
                    json={"model": self._model, "inputs": texts},
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise ValueError(f"Embedding failed: {data.get('errorMessage', data)}")
                return data["data"]["embeddings"]
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("JLL embed attempt %d failed (%d texts): %s — retrying in %ds",
                               attempt + 1, len(texts), exc, wait)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise


class OpenAIEmbedClient:
    """Embed client for any OpenAI-compatible embeddings endpoint.

    Works with: OpenAI, Azure OpenAI, Ollama, any standard /v1/embeddings endpoint.
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._model = model
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "no-key",
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                )
                return [item.embedding for item in resp.data]
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("OpenAI embed attempt %d failed (%d texts): %s — retrying in %ds",
                               attempt + 1, len(texts), exc, wait)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise


def make_embed_client() -> JLLEmbedClient | OpenAIEmbedClient:
    """Factory: reads config and returns the right embed driver."""
    from brn_daemon.config import load_config, get_embed_api_key
    cfg = load_config()
    ep = cfg.embed_provider
    api_key = get_embed_api_key() or ""
    if ep.type == "jll":
        return JLLEmbedClient(base_url=ep.base_url, api_key=api_key, model=ep.model)
    return OpenAIEmbedClient(base_url=ep.base_url, api_key=api_key, model=ep.model)
