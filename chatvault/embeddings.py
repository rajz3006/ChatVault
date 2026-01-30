"""Embedding generation and ChromaDB vector store for ChatVault.

Handles two collections:
- conversation_topics: conversation-level semantic chunks
- message_chunks: per-message (and sub-message) chunks for fine-grained retrieval
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Callable

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from chatvault.db import Database

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
import os

DEFAULT_DB_PATH = os.environ.get("CHATVAULT_DB_PATH", "chatvault.db")
DEFAULT_CHROMA_DIR = os.environ.get("CHATVAULT_CHROMA_DIR", "chroma_data")
MODEL_NAME = "all-MiniLM-L6-v2"
MAX_CHUNK_CHARS = 1600
CHUNK_OVERLAP = 200
LONG_MESSAGE_THRESHOLD = 2000  # ~500 tokens * 4 chars


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split long text into overlapping chunks.

    Args:
        text: The text to split.
        max_chars: Maximum characters per chunk.
        overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        A list of text chunks. Returns a single-element list if text is short enough.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start += max_chars - overlap
    return chunks


# ---------------------------------------------------------------------------
# EmbeddingEngine
# ---------------------------------------------------------------------------

class EmbeddingEngine:
    """Manages ChromaDB collections and embedding generation for ChatVault."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        chroma_dir: str | Path = DEFAULT_CHROMA_DIR,
    ) -> None:
        """Initialise the engine with a SQLite database and ChromaDB directory.

        Args:
            db_path: Path to the ChatVault SQLite database.
            chroma_dir: Directory for ChromaDB persistent storage.
        """
        self.db = Database(db_path)
        self.chroma_dir = Path(chroma_dir)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        self._ef = SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
        self._client = chromadb.PersistentClient(path=str(self.chroma_dir))

        self.conv_collection = self._client.get_or_create_collection(
            name="conversation_topics",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        self.msg_collection = self._client.get_or_create_collection(
            name="message_chunks",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_all(self, force: bool = False, progress_callback: Callable[[int, int, str], None] | None = None) -> dict[str, int]:
        """Embed all conversations and messages.

        Args:
            force: If True, delete existing collections and re-embed everything.

        Returns:
            Dict with counts of newly embedded items per collection.
        """
        if force:
            print("[embeddings] Force mode — deleting existing collections...")
            self._client.delete_collection("conversation_topics")
            self._client.delete_collection("message_chunks")
            self.conv_collection = self._client.get_or_create_collection(
                name="conversation_topics",
                embedding_function=self._ef,
                metadata={"hnsw:space": "cosine"},
            )
            self.msg_collection = self._client.get_or_create_collection(
                name="message_chunks",
                embedding_function=self._ef,
                metadata={"hnsw:space": "cosine"},
            )

        conv_count = self.embed_conversations(progress_callback=progress_callback)
        msg_count = self.embed_messages(progress_callback=progress_callback)
        return {"conversations": conv_count, "messages": msg_count}

    def embed_conversations(self, progress_callback: Callable[[int, int, str], None] | None = None) -> int:
        """Create conversation-level embeddings.

        Each conversation is represented by its name, summary, and the first
        two human messages concatenated into a single document.

        Returns:
            Number of newly embedded conversations.
        """
        conversations = self.db.get_all_conversations()
        existing_ids = set(self.conv_collection.get()["ids"]) if self.conv_collection.count() > 0 else set()

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for conv in conversations:
            doc_id = f"conv-{conv['uuid']}"
            if doc_id in existing_ids:
                continue

            # Build document text
            parts: list[str] = []
            if conv.get("name"):
                parts.append(conv["name"])
            if conv.get("summary"):
                parts.append(conv["summary"])

            # First two human messages
            messages = self.db.get_conversation_messages(conv["uuid"])
            human_msgs = [m for m in messages if m["sender"] == "human"]
            for m in human_msgs[:2]:
                if m.get("text"):
                    parts.append(m["text"][:800])  # cap each contribution

            doc_text = "\n\n".join(parts).strip()
            if not doc_text:
                continue

            ids.append(doc_id)
            documents.append(doc_text)
            metadatas.append({
                "conversation_uuid": conv["uuid"],
                "conversation_name": conv.get("name") or "",
                "source_id": conv.get("source_id", ""),
                "date": conv.get("created_at") or "",
            })

        if not ids:
            print("[embeddings] No new conversations to embed.")
            return 0

        print(f"[embeddings] Embedding {len(ids)} conversations...")
        self._batch_add(self.conv_collection, ids, documents, metadatas, label="conversations", progress_callback=progress_callback)
        return len(ids)

    def embed_messages(self, progress_callback: Callable[[int, int, str], None] | None = None) -> int:
        """Create message-level embeddings for all assistant messages.

        Long messages are split into overlapping chunks.

        Returns:
            Number of newly embedded message chunks.
        """
        # Fetch all assistant messages with conversation info
        rows = self.db.conn.execute("""
            SELECT m.uuid, m.conversation_uuid, m.sender, m.text, m.created_at,
                   c.name AS conversation_name, c.source_id
            FROM messages m
            JOIN conversations c ON m.conversation_uuid = c.uuid
            WHERE m.sender = 'assistant' AND m.text IS NOT NULL AND m.text != ''
        """).fetchall()

        existing_ids = set(self.msg_collection.get()["ids"]) if self.msg_collection.count() > 0 else set()

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for row in rows:
            row_d = dict(row)
            text = row_d["text"]
            base_id = f"msg-{row_d['uuid']}"

            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                chunk_id = base_id if len(chunks) == 1 else f"{base_id}-c{i}"
                if chunk_id in existing_ids:
                    continue

                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    "conversation_uuid": row_d["conversation_uuid"],
                    "message_uuid": row_d["uuid"],
                    "sender": row_d["sender"],
                    "date": row_d.get("created_at") or "",
                    "conversation_name": row_d.get("conversation_name") or "",
                    "source_id": row_d.get("source_id") or "",
                })

        if not ids:
            print("[embeddings] No new message chunks to embed.")
            return 0

        print(f"[embeddings] Embedding {len(ids)} message chunks...")
        self._batch_add(self.msg_collection, ids, documents, metadatas, label="messages", progress_callback=progress_callback)
        return len(ids)

    def query_similar(
        self,
        query_text: str,
        collection: str = "message_chunks",
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search for similar documents in a collection.

        Args:
            query_text: The text to search for.
            collection: Which collection to query ('conversation_topics' or 'message_chunks').
            n_results: Number of results to return.
            where: Optional ChromaDB where filter dict.

        Returns:
            Raw ChromaDB query result dict with ids, documents, metadatas, distances.
        """
        col = self.conv_collection if collection == "conversation_topics" else self.msg_collection
        kwargs: dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return col.query(**kwargs)

    def get_stats(self) -> dict[str, int]:
        """Return the number of vectors in each collection.

        Returns:
            Dict mapping collection name to document count.
        """
        return {
            "conversation_topics": self.conv_collection.count(),
            "message_chunks": self.msg_collection.count(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _batch_add(
        self,
        collection: Any,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        label: str = "items",
        batch_size: int = 256,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        """Add documents to a ChromaDB collection in batches with progress."""
        total = len(ids)
        t0 = time.time()
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
            if progress_callback is not None:
                progress_callback(end, total, label)
            if end % 100 < batch_size or end == total:
                elapsed = time.time() - t0
                print(f"  [{label}] {end}/{total} embedded ({elapsed:.1f}s)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run embedding generation from the command line."""
    parser = argparse.ArgumentParser(description="ChatVault embedding generator")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--chroma-dir", default=DEFAULT_CHROMA_DIR, help="ChromaDB storage directory")
    parser.add_argument("--force", action="store_true", help="Re-embed everything from scratch")
    args = parser.parse_args()

    print(f"[embeddings] DB: {args.db} | ChromaDB: {args.chroma_dir} | Force: {args.force}")
    engine = EmbeddingEngine(db_path=args.db, chroma_dir=args.chroma_dir)

    results = engine.embed_all(force=args.force)
    stats = engine.get_stats()

    print(f"\n[embeddings] Done. New embeddings: {results}")
    print(f"[embeddings] Collection totals: {stats}")


if __name__ == "__main__":
    main()
