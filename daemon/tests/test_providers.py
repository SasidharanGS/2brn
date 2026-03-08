import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from brn_daemon.providers import JLLEmbedClient, OpenAIEmbedClient


@pytest.fixture
def jll_client():
    return JLLEmbedClient(base_url="http://localhost:8889", api_key="test-token", model="TEXT_EMBEDDING_3_LARGE")


@pytest.fixture
def openai_client():
    return OpenAIEmbedClient(base_url="http://localhost:8889/v1", api_key="test-token", model="text-embedding-3-large")


async def test_jll_embed_batch_returns_list_of_lists(jll_client):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "success": True,
        "data": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    })
    with patch.object(jll_client._http, "post", AsyncMock(return_value=mock_resp)) as mock_post:
        result = await jll_client.embed_batch(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json["inputs"] == ["hello", "world"]


async def test_jll_embed_single_returns_list(jll_client):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "success": True,
        "data": {"embeddings": [[0.5, 0.6]]}
    })
    with patch.object(jll_client._http, "post", AsyncMock(return_value=mock_resp)):
        result = await jll_client.embed("hello")
    assert result == [0.5, 0.6]


async def test_jll_embed_batch_retries_on_failure(jll_client):
    call_count = 0
    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("connection error")
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"success": True, "data": {"embeddings": [[0.1]]}})
        return mock_resp
    with patch.object(jll_client._http, "post", flaky):
        with patch("brn_daemon.providers.asyncio.sleep", AsyncMock()):
            result = await jll_client.embed_batch(["hello"])
    assert result == [[0.1]]
    assert call_count == 2


async def test_openai_embed_batch_returns_list_of_lists(openai_client):
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])]
    with patch.object(openai_client._client.embeddings, "create", AsyncMock(return_value=mock_resp)):
        result = await openai_client.embed_batch(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


async def test_openai_embed_single_returns_list(openai_client):
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.7, 0.8])]
    with patch.object(openai_client._client.embeddings, "create", AsyncMock(return_value=mock_resp)):
        result = await openai_client.embed("hello")
    assert result == [0.7, 0.8]
