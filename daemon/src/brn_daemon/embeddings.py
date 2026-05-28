import asyncio
import logging

import aiosqlite
import chromadb
from chromadb.config import Settings

from brn_daemon.db import get_brn_home, get_db_path

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
        self._count: int = 0

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
        self._count += 1

    async def query(self, embedding: list[float], n_results: int = 10,
              where: dict | None = None) -> dict:
        if self._count == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        actual_n = min(n_results, self._count)
        kwargs: dict = {
            "query_embeddings": [embedding],
            "n_results": actual_n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        loop = asyncio.get_running_loop()
        try:
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
            async with aiosqlite.connect(get_db_path()) as conn:
                await conn.execute(
                    "UPDATE activities SET chroma_id = ? WHERE id = ?",
                    (doc_id, activity_id),
                )
                await conn.commit()
        except Exception:
            logger.exception("Failed to embed activity %d", activity_id)
