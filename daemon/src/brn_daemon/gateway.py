import asyncio
import logging
import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "GPT_5_2"
_DEFAULT_EMBED_MODEL = "TEXT_EMBEDDING_3_LARGE"
_MAX_RETRIES = 3


class GatewayClient:
    def __init__(self, base_url: str, token: str, llm_model: str = _DEFAULT_MODEL, embed_model: str = _DEFAULT_EMBED_MODEL):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._llm_model = llm_model
        self._embed_model = embed_model
        self._client = AsyncOpenAI(
            base_url=f"{self._base_url}/v1",
            api_key=token or "no-token",
        )
        # Reuse one HTTP client for all embedding calls — avoids per-call TCP setup
        self._http = httpx.AsyncClient(
            timeout=30,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        """Close the shared HTTP client. Call on daemon shutdown."""
        await self._http.aclose()

    async def chat_complete(
        self,
        messages: list[dict],
        model: str = None,
    ) -> str:
        """Non-streaming chat completion. For streaming use chat_stream()."""
        model = model or self._llm_model
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=False,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(
                    "Gateway attempt %d failed: %s — retrying in %ds",
                    attempt + 1, exc, wait,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise

    async def chat_stream(self, messages: list[dict], model: str = None):
        model = model or self._llm_model
        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, text: str, model: str = None) -> list[float]:
        """Embed a single text string. For bulk use, prefer embed_batch()."""
        results = await self.embed_batch([text], model=model)
        return results[0]

    async def embed_batch(self, texts: list[str], model: str = None) -> list[list[float]]:
        """Embed multiple texts in one HTTP call.

        JLL Gateway uses a non-OpenAI format:
          Request:  {"model": "...", "inputs": ["text1", "text2", ...]}
          Response: {"success": true, "data": {"embeddings": [[...], [...]]}}
        """
        model = model or self._embed_model
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._http.post(
                    f"{self._base_url}/v1/embeddings",
                    json={"model": model, "inputs": texts},
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise ValueError(f"Embedding failed: {data.get('errorMessage', data)}")
                return data["data"]["embeddings"]
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(
                    "Embed attempt %d failed (%d texts): %s — retrying in %ds",
                    attempt + 1, len(texts), exc, wait,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise


def make_gateway_client() -> "GatewayClient":
    from brn_daemon.config import load_config, get_gateway_token
    cfg = load_config()
    token = get_gateway_token() or ""
    return GatewayClient(
        base_url=cfg.gateway_url,
        token=token,
        llm_model=cfg.llm_model,
        embed_model=cfg.embed_model,
    )
