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


async def test_rag_distance_cutoff_filters_high_distance_docs():
    """Documents with distance > DISTANCE_CUTOFF must be excluded from context."""
    from brn_daemon.chat import ChatService, DISTANCE_CUTOFF

    async def fake_embed(text):
        return [0.1] * 384

    async def fake_stream(messages):
        # Capture the prompt to inspect context chunks
        user_msg = messages[-1]["content"]
        yield "response"
        fake_stream.last_prompt = user_msg

    fake_stream.last_prompt = ""

    fake_store = MagicMock()
    # Activity results: one close doc (distance 0.3) and one far doc (distance 0.95)
    fake_store.query = AsyncMock(return_value={
        "documents": [["close doc", "far doc"]],
        "metadatas": [[
            {"source": "activity", "timestamp": "2026-05-28T10:00:00", "app_name": "Safari", "date": "2026-05-28"},
            {"source": "activity", "timestamp": "2026-05-28T11:00:00", "app_name": "Finder", "date": "2026-05-28"},
        ]],
        "distances": [[0.3, 0.95]],
    })
    fake_store.query_notes = AsyncMock(return_value={
        "documents": [[]], "metadatas": [[]], "distances": [[]]
    })

    embed_client = MagicMock()
    embed_client.embed = fake_embed

    svc = ChatService(
        chat_fn=MagicMock(),
        stream_fn=fake_stream,
        embed_client=embed_client,
        chroma_store=fake_store,
    )

    chunks = []
    async for chunk in svc.chat("what did I do?"):
        chunks.append(chunk)

    assert DISTANCE_CUTOFF < 0.95  # sanity
    assert "far doc" not in fake_stream.last_prompt
    assert "close doc" in fake_stream.last_prompt


async def test_chat_category_filter_single_vs_multi():
    """One category scopes the activity query with $eq; several use $in."""
    async def fake_embed(text):
        return [0.1] * 384

    async def fake_stream(messages):
        yield "ok"

    embed_client = MagicMock()
    embed_client.embed = fake_embed

    store = MagicMock()
    store.query = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})
    store.query_notes = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})

    svc = ChatService(chat_fn=MagicMock(), stream_fn=fake_stream, embed_client=embed_client, chroma_store=store)

    # several categories → $in
    async for _ in svc.chat("q", categories=["work", "research"]):
        pass
    assert store.query.call_args.kwargs["where"]["task_category"] == {"$in": ["work", "research"]}

    # a single category → $eq (preserves the original single-filter semantics)
    store.query.reset_mock()
    async for _ in svc.chat("q", categories=["work"]):
        pass
    assert store.query.call_args.kwargs["where"]["task_category"] == {"$eq": "work"}

    # no categories → no task_category constraint at all
    store.query.reset_mock()
    async for _ in svc.chat("q"):
        pass
    assert store.query.call_args.kwargs["where"] is None
