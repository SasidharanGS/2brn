import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from brn_daemon.llm import chat_complete, chat_stream, make_chat_kwargs


def test_make_chat_kwargs_openai_compatible():
    kwargs = make_chat_kwargs(
        provider_type="openai_compatible",
        base_url="http://localhost:8889/v1",
        api_key="mykey",
        model="GPT_5_2",
        extra_headers={},
    )
    assert kwargs["model"] == "openai/GPT_5_2"
    assert kwargs["api_key"] == "mykey"
    assert kwargs["base_url"] == "http://localhost:8889/v1"


def test_make_chat_kwargs_anthropic():
    kwargs = make_chat_kwargs(
        provider_type="anthropic",
        base_url="https://example.com/anthropic/v1",
        api_key="sk-ant-xyz",
        model="claude-sonnet-4-6",
        extra_headers={"api-key": "sk-ant-xyz"},
    )
    assert kwargs["model"] == "anthropic/claude-sonnet-4-6"
    assert kwargs["extra_headers"] == {"api-key": "sk-ant-xyz"}


def test_make_chat_kwargs_ollama():
    kwargs = make_chat_kwargs(
        provider_type="ollama",
        base_url="http://localhost:11434",
        api_key="",
        model="llama3",
        extra_headers={},
    )
    assert kwargs["model"] == "ollama/llama3"


async def test_chat_complete_returns_string():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "hello"
    with patch("brn_daemon.llm.litellm.acompletion", AsyncMock(return_value=mock_resp)):
        result = await chat_complete(
            messages=[{"role": "user", "content": "hi"}],
            provider_type="openai_compatible",
            base_url="http://localhost:8889/v1",
            api_key="1",
            model="GPT_5_2",
            extra_headers={},
        )
    assert result == "hello"


async def test_chat_complete_retries_on_failure():
    call_count = 0
    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("rate limit")
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        return mock_resp
    with patch("brn_daemon.llm.litellm.acompletion", flaky):
        with patch("brn_daemon.llm.asyncio.sleep", AsyncMock()):
            result = await chat_complete(
                messages=[{"role": "user", "content": "hi"}],
                provider_type="openai_compatible",
                base_url="http://localhost:8889/v1",
                api_key="1",
                model="GPT_5_2",
                extra_headers={},
            )
    assert result == "ok"
    assert call_count == 3
