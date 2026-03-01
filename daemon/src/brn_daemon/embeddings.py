import logging
import aiosqlite
import chromadb
from chromadb.config import Settings
from pathlib import Path

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

    @property
    def collection(self):
        return self._collection

    @property
    def note_collection(self):
        return self._note_collection

    @property
    def chroma_client(self):
        return self._client

    def add(self, doc_id: str, text: str, metadata: dict, embedding: list[float]) -> None:
        self._collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
            embeddings=[embedding],
        )

    def query(self, embedding: list[float], n_results: int = 10,
              where: dict | None = None) -> dict:
        try:
            count = self._collection.count()
            if count == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            actual_n = min(n_results, count)
            kwargs = {
                "query_embeddings": [embedding],
                "n_results": actual_n,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where
            return self._collection.query(**kwargs)
        except Exception as exc:
            logger.warning("Activity collection query failed: %s", exc)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def query_notes(self, embedding: list[float], n_results: int = 5) -> dict:
        """Query the note_memories collection."""
        try:
            count = self._note_collection.count()
            if count == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            actual_n = min(n_results, count)
            return self._note_collection.query(
                query_embeddings=[embedding],
                n_results=actual_n,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("Note collection query failed: %s", exc)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


class EmbeddingService:
    def __init__(self, gateway, chroma_store: ChromaStore):
        self._gateway = gateway
        self._store = chroma_store

    async def embed_activity(self, activity_id: int, summary: str, metadata: dict) -> None:
        try:
            embedding = await self._gateway.embed(summary)
            doc_id = f"activity-{activity_id}"
            self._store.add(doc_id=doc_id, text=summary, metadata=metadata, embedding=embedding)
            async with aiosqlite.connect(get_db_path()) as conn:
                await conn.execute(
                    "UPDATE activities SET chroma_id = ? WHERE id = ?",
                    (doc_id, activity_id),
                )
                await conn.commit()
        except Exception as exc:
            logger.error("Failed to embed activity %d: %s", activity_id, exc)
