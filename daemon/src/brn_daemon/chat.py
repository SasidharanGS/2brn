import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are a personal second brain assistant.
You help the user recall what they did on their computer and what they've noted in their knowledge vault.
Answer questions based ONLY on the provided context.
If context is insufficient, say so honestly.
Be concise, specific, and cite dates/apps/note sources when relevant.
Each context entry includes a precise Time field (YYYY-MM-DD HH:MM in UTC). Use these timestamps to
determine order and recency — e.g. the last activity of a day is the one with the latest time."""


def build_rag_prompt(question: str, context_chunks: list[dict]) -> str:
    if not context_chunks:
        return (
            f"Context: No recorded activities or notes found for this query.\n\n"
            f"User question: {question}\n\n"
            f"Answer honestly that there is no recorded context for this query."
        )
    def _fmt_timestamp(meta: dict) -> str:
        ts = meta.get("timestamp") or meta.get("date", "?")
        # Convert ISO UTC timestamp to a readable local-ish label, e.g. "2026-04-27 22:47"
        if ts and "T" in ts:
            ts = ts[:16].replace("T", " ")
        return ts

    context_text = "\n\n".join(
        f"[{i+1}] Source: {c['metadata'].get('source','activity')} | "
        f"Time: {_fmt_timestamp(c['metadata'])} | "
        f"App/Note: {c['metadata'].get('app_name') or c['metadata'].get('title','?')}"
        f"{' (' + c['metadata']['notebook'] + ')' if c['metadata'].get('notebook') else ''}"
        f"\n{c['text']}"
        for i, c in enumerate(context_chunks)
    )
    return f"Context from your activity history and notes:\n\n{context_text}\n\nUser question: {question}"


class ChatService:
    def __init__(self, chat_fn, stream_fn, embed_client, chroma_store):
        self._chat_fn = chat_fn
        self._stream_fn = stream_fn
        self._embed_client = embed_client
        self._store = chroma_store

    async def chat(
        self,
        question: str,
        date_filter: str | None = None,
        category_filter: str | None = None,
        n_results: int = 10,
    ) -> AsyncIterator[str]:
        # 1. Embed the query
        try:
            query_embedding = await self._embed_client.embed(question)
        except Exception as exc:
            logger.error("Failed to embed query: %s", exc)
            yield "Sorry, I couldn't process your question right now."
            return

        # 2. Build ChromaDB where filter for activity memories
        where = {}
        if date_filter:
            where["date"] = {"$eq": date_filter}
        if category_filter:
            where["task_category"] = {"$eq": category_filter}

        # 3. Semantic search in activity_memories
        try:
            results = self._store.query(
                embedding=query_embedding,
                n_results=n_results,
                where=where if where else None,
            )
        except Exception as exc:
            logger.error("ChromaDB activity query failed: %s", exc)
            results = {"documents": [[]], "metadatas": [[]]}

        # 4. Also search note_memories
        try:
            note_results = self._store.query_notes(
                embedding=query_embedding,
                n_results=5,
            )
        except Exception as exc:
            logger.warning("ChromaDB note query failed: %s", exc)
            note_results = {"documents": [[]], "metadatas": [[]]}

        # 5. Build context chunks from both sources
        context_chunks = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            context_chunks.append({"text": doc, "metadata": meta})

        note_docs = note_results.get("documents", [[]])[0]
        note_metas = note_results.get("metadatas", [[]])[0]
        for doc, meta in zip(note_docs, note_metas):
            context_chunks.append({"text": doc, "metadata": meta})

        # 6. Build and stream RAG response
        user_prompt = build_rag_prompt(question, context_chunks)
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        async for chunk in self._stream_fn(messages):
            yield chunk
