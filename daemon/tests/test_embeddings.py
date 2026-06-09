import pytest
import asyncio
import inspect
import aiosqlite
from unittest.mock import AsyncMock, MagicMock
from brn_daemon.embeddings import EmbeddingService, ChromaStore

@pytest.fixture
def chroma_store(tmp_home):
    return ChromaStore(persist_dir=str(tmp_home / "chroma"))

@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.embed = AsyncMock(return_value=[0.1] * 384)
    return gw

def test_chroma_store_initialises(chroma_store):
    col = chroma_store.collection
    assert col is not None
    assert col.name == "activity_memories"

async def test_chroma_store_add_and_query(chroma_store):
    await chroma_store.add(
        doc_id="test-1",
        text="writing Python code in VS Code",
        metadata={"timestamp": "2026-04-12T10:00:00", "app_name": "Code",
                  "tags": "coding,python", "date": "2026-04-12",
                  "task_category": "work", "productivity_state": "focused"},
        embedding=[0.1] * 384,
    )
    results = await chroma_store.query(embedding=[0.1] * 384, n_results=1)
    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "test-1"

async def test_embedding_service_writes_chroma_id_to_db(tmp_home, mock_gateway):
    from brn_daemon.db import init_db, get_db_path
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger) VALUES (datetime('now'), 'heartbeat')"
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        cap_id = (await cur.fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
            "task_category_confidence, productivity_state, productivity_confidence) "
            "VALUES (?, datetime('now'), 'coding', '[]', 'work', 0.9, 'focused', 0.8)",
            (cap_id,)
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        act_id = (await cur.fetchone())[0]

    store = ChromaStore(persist_dir=str(tmp_home / "chroma"))
    mock_embed_client = MagicMock()
    mock_embed_client.embed = AsyncMock(return_value=[0.1] * 384)
    service = EmbeddingService(embed_client=mock_embed_client, chroma_store=store)
    await service.embed_activity(
        activity_id=act_id,
        summary="coding in VS Code",
        metadata={"timestamp": "2026-04-12T10:00:00", "app_name": "Code",
                  "tags": "coding", "date": "2026-04-12",
                  "task_category": "work", "productivity_state": "focused"},
    )

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT chroma_id FROM activities WHERE id = ?", (act_id,))
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == f"activity-{act_id}"
    assert store.collection.count() == 1


async def test_chroma_store_add_is_awaitable(tmp_home):
    from brn_daemon.embeddings import ChromaStore
    store = ChromaStore()
    assert inspect.iscoroutinefunction(store.add), "ChromaStore.add must be async"


async def test_chroma_store_query_is_awaitable(tmp_home):
    from brn_daemon.embeddings import ChromaStore
    store = ChromaStore()
    assert inspect.iscoroutinefunction(store.query), "ChromaStore.query must be async"


async def test_chroma_store_query_works_after_restart(tmp_home):
    """Regression for F-RAG-1: a fresh ChromaStore (as after a daemon restart)
    must see documents persisted by a previous run. query() reads the live
    collection count rather than an in-process counter that reset to 0 on every
    start — the cached counter silently returned empty activity RAG results
    (and capped n_results to the in-session count) until new activities embedded.
    """
    persist = str(tmp_home / "chroma")
    store1 = ChromaStore(persist_dir=persist)
    await store1.add(
        doc_id="act-1",
        text="reviewing a pull request on GitHub",
        metadata={"date": "2026-05-28", "source": "activity"},
        embedding=[0.1] * 384,
    )

    # Simulate a daemon restart: a brand-new store over the same persisted dir.
    store2 = ChromaStore(persist_dir=persist)
    results = await store2.query(embedding=[0.1] * 384, n_results=5)
    assert results["ids"][0], "query after restart must return persisted docs"
    assert results["ids"][0][0] == "act-1"
