import pytest
from unittest.mock import AsyncMock, MagicMock
from brn_daemon.chat import build_rag_prompt, ChatService

def test_build_rag_prompt_includes_question_and_context():
    context_chunks = [
        {"text": "User was coding in VS Code", "metadata": {"date": "2026-04-12", "app_name": "Code"}},
        {"text": "User reviewed pull requests on GitHub", "metadata": {"date": "2026-04-12", "app_name": "Chrome"}},
    ]
    prompt = build_rag_prompt(
        question="What was I working on last Tuesday?",
        context_chunks=context_chunks,
    )
    assert "VS Code" in prompt
    assert "pull requests" in prompt
    assert "What was I working on" in prompt

def test_build_rag_prompt_no_context():
    prompt = build_rag_prompt(question="What did I do today?", context_chunks=[])
    assert "What did I do today?" in prompt
    assert "no recorded" in prompt.lower() or "no context" in prompt.lower() or "no recorded" in prompt.lower()

async def test_chat_service_streams_answer(tmp_home):
    from brn_daemon.db import init_db
    await init_db()

    mock_embed_client = MagicMock()
    mock_embed_client.embed = AsyncMock(return_value=[0.1] * 384)

    mock_chroma = MagicMock()
    mock_chroma.query = MagicMock(return_value={
        "ids": [["activity-1"]],
        "documents": [["coding in Python"]],
        "metadatas": [[{"date": "2026-04-12", "app_name": "Code", "task_category": "work",
                        "productivity_state": "focused", "tags": "coding", "timestamp": "2026-04-12T10:00:00"}]],
        "distances": [[0.1]],
    })

    chunks_seen = []
    async def fake_stream(messages):
        for chunk in ["Here ", "is ", "your ", "answer."]:
            chunks_seen.append(chunk)
            yield chunk

    service = ChatService(chat_fn=AsyncMock(), stream_fn=fake_stream, embed_client=mock_embed_client, chroma_store=mock_chroma)
    collected = []
    async for chunk in service.chat(question="What was I doing?"):
        collected.append(chunk)

    assert "".join(collected) == "Here is your answer."
    mock_chroma.query.assert_called_once()
