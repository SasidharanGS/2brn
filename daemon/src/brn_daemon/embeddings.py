import asyncio
import logging

import chromadb
from chromadb.config import Settings

from brn_daemon.db import get_brn_home, get_conn

logger = logging.getLogger(__name__)

COLLECTION_NAME = "activity_memories"
NOTE_COLLECTION_NAME = "note_memories"


class ChromaStore:
    def __init__(self, persist_dir: str | None = None):
        dir_path = persist_dir or str(get_brn_home() / "chroma")
        self._client = chromadb.PersistentClient(
            path=dir_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._note_collection = self._client.get_or_create_collection(
            name=NOTE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self):
        return self._collection

    @property
    def note_collection(self):
        return self._note_collection

    @property
    def chroma_client(self):
        return self._client

    async def add(self, doc_id: str, text: str, metadata: dict, embedding: list[float]) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
                embeddings=[embedding],
            ),
        )

    async def add_note(self, doc_id: str, text: str, metadata: dict, embedding: list[float]) -> None:
        """Upsert a document into the note_memories collection (off the event loop).

        Used for externally-ingested notes (Joplin, and the mobile share-sheet),
        which live alongside Joplin notes so chat RAG can retrieve them.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._note_collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
                embeddings=[embedding],
            ),
        )

    async def query(self, embedding: list[float], n_results: int = 10,
              where: dict | None = None) -> dict:
        loop = asyncio.get_running_loop()
        try:
            # Read the count live from the collection rather than an in-process
            # cache: it must reflect documents persisted by previous daemon runs,
            # not just adds made since this process started. (A cached counter
            # reset to 0 on every restart, silently emptying activity RAG.)
            count = await loop.run_in_executor(None, self._collection.count)
            if count == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            actual_n = min(n_results, count)
            kwargs: dict = {
                "query_embeddings": [embedding],
                "n_results": actual_n,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where
            return await loop.run_in_executor(  # type: ignore[return-value]
                None, lambda: self._collection.query(**kwargs)
            )
        except Exception:
            logger.exception("Activity collection query failed")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    async def query_notes(self, embedding: list[float], n_results: int = 5) -> dict:
        """Query the note_memories collection."""
        loop = asyncio.get_running_loop()
        try:
            count = await loop.run_in_executor(None, self._note_collection.count)
            if count == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            actual_n = min(n_results, count)
            return await loop.run_in_executor(  # type: ignore[return-value]
                None,
                lambda: self._note_collection.query(
                    query_embeddings=[embedding],
                    n_results=actual_n,
                    include=["documents", "metadatas", "distances"],
                ),
            )
        except Exception:
            logger.exception("Note collection query failed")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


class EmbeddingService:
    def __init__(self, embed_client, chroma_store: ChromaStore | None):
        self._embed_client = embed_client
        self._store = chroma_store

    async def embed_activity(self, activity_id: int, summary: str, metadata: dict) -> None:
        try:
            if self._store is None:
                return
            embedding = await self._embed_client.embed(summary)
            doc_id = f"activity-{activity_id}"
            await self._store.add(doc_id=doc_id, text=summary, metadata=metadata, embedding=embedding)
            async with get_conn() as conn:
                await conn.execute(
                    "UPDATE activities SET chroma_id = ? WHERE id = ?",
                    (doc_id, activity_id),
                )
                await conn.commit()
        except Exception:
            logger.exception("Failed to embed activity %d", activity_id)

    async def embed_activities_batch(self, items: list[dict]) -> int:
        """Embed many activities in a single provider call, then upsert each into
        ChromaDB and set its chroma_id. ``items`` are dicts with keys
        ``activity_id``, ``summary``, ``metadata``. Returns the number embedded.

        Used by the manual re-sync so a large backlog isn't one network round-trip
        per row.
        """
        if self._store is None or not items:
            return 0
        summaries = [it["summary"] for it in items]
        try:
            embeddings = await self._embed_client.embed_batch(summaries)
        except Exception:
            logger.exception("Batch embed failed for %d activities", len(items))
            return 0
        async with get_conn() as conn:
            for it, emb in zip(items, embeddings):
                doc_id = f"activity-{it['activity_id']}"
                await self._store.add(
                    doc_id=doc_id, text=it["summary"], metadata=it["metadata"], embedding=emb,
                )
                await conn.execute(
                    "UPDATE activities SET chroma_id = ? WHERE id = ?",
                    (doc_id, it["activity_id"]),
                )
            await conn.commit()
        return len(items)
