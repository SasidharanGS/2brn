import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from brn_daemon.gateway import GatewayClient

@pytest.fixture
def client():
    return GatewayClient(base_url="http://localhost:8888", token="test-token")

async def test_chat_complete_returns_content(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"summary":"coding","tags":["python"],"task_category":"work","task_category_confidence":0.9,"productivity_state":"focused","productivity_confidence":0.85}'
    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
        result = await client.chat_complete([{"role": "user", "content": "test"}])
    assert result == mock_response.choices[0].message.content

async def test_embed_returns_list(client):
    # JLL Gateway returns {"success": true, "data": {"embeddings": [[...]]}}
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "success": True,
        "data": {"embeddings": [[0.1, 0.2, 0.3]]}
    })
    # Patch the persistent _http instance's post method; capture mock before exit
    mock_post = AsyncMock(return_value=mock_resp)
    with patch.object(client._http, "post", mock_post):
        result = await client.embed("hello world")
    assert result == [0.1, 0.2, 0.3]
    # Verify it used 'inputs' (array) not 'input'
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["inputs"] == ["hello world"]

async def test_embed_batch_returns_list_of_lists(client):
    """embed_batch sends all texts in one call and returns all embeddings."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "success": True,
        "data": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    })
    mock_post = AsyncMock(return_value=mock_resp)
    with patch.object(client._http, "post", mock_post):
        result = await client.embed_batch(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    # Only one HTTP call for two texts
    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["inputs"] == ["hello", "world"]

async def test_chat_complete_retries_on_failure(client):
    call_count = 0
    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("connection error")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        return mock_response
    with patch.object(client._client.chat.completions, "create", new=flaky):
        with patch("brn_daemon.gateway.asyncio.sleep", new=AsyncMock()):
            result = await client.chat_complete([{"role": "user", "content": "test"}])
    assert result == "ok"
    assert call_count == 3
