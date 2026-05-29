import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from brn_daemon.providers import CustomEmbedClient, OpenAIEmbedClient


@pytest.fixture
def custom_client():
    return CustomEmbedClient(base_url="http://localhost:9999", api_key="test-token", model="test-embed-model")


@pytest.fixture
def openai_client():
    return OpenAIEmbedClient(base_url="http://localhost:9999/v1", api_key="test-token", model="text-embedding-3-large")


async def test_custom_embed_batch_returns_list_of_lists(custom_client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"success": True, "data": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}})
    with patch.object(custom_client._http, "post", AsyncMock(return_value=mock_resp)) as mock_post:
        result = await custom_client.embed_batch(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_post.assert_awaited_once()


async def test_custom_embed_single_returns_list(custom_client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"success": True, "data": {"embeddings": [[0.1, 0.2]]}})
    with patch.object(custom_client._http, "post", AsyncMock(return_value=mock_resp)):
        result = await custom_client.embed("hello")
    assert result == [0.1, 0.2]


async def test_custom_embed_batch_retries_on_failure(custom_client):
    call_count = 0

    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.HTTPError("transient error")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"success": True, "data": {"embeddings": [[0.5]]}})
        return mock_resp

    with patch.object(custom_client._http, "post", flaky):
        with patch("brn_daemon.providers.asyncio.sleep", AsyncMock()):
            result = await custom_client.embed_batch(["hello"])
    assert result == [[0.5]]
    assert call_count == 3


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
