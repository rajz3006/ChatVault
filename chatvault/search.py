"""Hybrid search engine for ChatVault — semantic + FTS5 keyword search."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatvault.db import Database
from chatvault.embeddings import EmbeddingEngine, DEFAULT_DB_PATH, DEFAULT_CHROMA_DIR


@dataclass
class SearchResult:
    """A single search result."""

    conversation_uuid: str
    message_uuid: str
    conversation_name: str
    text: str
    score: float
    source_id: str = ""
    sender: str = ""
    created_at: str = ""


class SearchEngine:
    """Hybrid search combining ChromaDB semantic search and SQLite FTS5."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        chroma_dir: str | Path = DEFAULT_CHROMA_DIR,
    ) -> None:
        """Initialise search engine with database and embedding engine.

        Args:
            db_path: Path to the ChatVault SQLite database.
            chroma_dir: Directory for ChromaDB persistent storage.
        """
        self.db = Database(db_path)
        self.engine = EmbeddingEngine(db_path=db_path, chroma_dir=chroma_dir)

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def semantic_search(
        self,
        query: str,
        n: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search both ChromaDB collections and merge results.

        Args:
            query: The search query text.
            n: Maximum number of results to return.
            filters: Optional filter dict with keys: source_id, sender, date_from, date_to.

        Returns:
            List of SearchResult sorted by distance (ascending = most similar).
        """
        where = self._build_chroma_where(filters) if filters else None

        # Query both collections
        msg_results = self.engine.query_similar(
            query, collection="message_chunks", n_results=n, where=where,
        )
        conv_results = self.engine.query_similar(
            query, collection="conversation_topics", n_results=n, where=where,
        )

        results: list[SearchResult] = []
        results.extend(self._parse_chroma_results(msg_results))
        results.extend(self._parse_chroma_results(conv_results))

        # Sort by distance (lower = better), deduplicate by message_uuid
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in sorted(results, key=lambda x: x.score):
            key = r.message_uuid or r.conversation_uuid
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        return deduped[:n]

    # ------------------------------------------------------------------
    # Keyword search (FTS5)
    # ------------------------------------------------------------------

    def keyword_search(self, query: str, n: int = 10) -> list[SearchResult]:
        """Full-text search using SQLite FTS5.

        Args:
            query: The search query text.
            n: Maximum number of results to return.

        Returns:
            List of SearchResult sorted by FTS5 rank.
        """
        # Build FTS5 query scoped to the text column only
        words = [word for word in query.split() if word.strip()]
        fts_query = " OR ".join(f"text:{word}" for word in words)
        if not fts_query:
            return []

        try:
            rows = self.db.conn.execute(
                """
                SELECT m.uuid AS message_uuid, m.conversation_uuid,
                       m.sender, m.text, m.created_at,
                       c.name AS conversation_name, c.source_id,
                       rank
                FROM messages_fts
                JOIN messages m ON m.rowid = messages_fts.rowid
                JOIN conversations c ON m.conversation_uuid = c.uuid
                WHERE messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, n),
            ).fetchall()
        except Exception:
            return []

        results: list[SearchResult] = []
        for row in rows:
            d = dict(row)
            results.append(SearchResult(
                conversation_uuid=d["conversation_uuid"],
                message_uuid=d["message_uuid"],
                conversation_name=d.get("conversation_name") or "",
                text=d.get("text") or "",
                score=0.0,  # FTS rank is used for ordering only; RRF assigns final score
                source_id=d.get("source_id") or "",
                sender=d.get("sender") or "",
                created_at=d.get("created_at") or "",
            ))
        return results

    # ------------------------------------------------------------------
    # Hybrid search (RRF)
    # ------------------------------------------------------------------

    def hybrid_search(
        self,
        query: str,
        n: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Combine semantic and keyword search using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) across methods, k = 60.

        Args:
            query: The search query text.
            n: Maximum number of results to return.
            filters: Optional filter dict.

        Returns:
            List of SearchResult sorted by RRF score (descending).
        """
        k = 60
        semantic_results = self.semantic_search(query, n=n * 2, filters=filters)
        keyword_results = self.keyword_search(query, n=n * 2)

        # Build RRF scores keyed by (conversation_uuid, message_uuid)
        scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        for rank, r in enumerate(semantic_results, start=1):
            key = r.message_uuid or r.conversation_uuid
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            result_map[key] = r

        for rank, r in enumerate(keyword_results, start=1):
            key = r.message_uuid or r.conversation_uuid
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in result_map:
                result_map[key] = r

        # Sort by RRF score descending
        sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
        final: list[SearchResult] = []
        for key in sorted_keys[:n]:
            r = result_map[key]
            r.score = scores[key]
            final.append(r)

        return final

    # ------------------------------------------------------------------
    # Reranked search
    # ------------------------------------------------------------------

    def reranked_search(
        self,
        query: str,
        n: int = 5,
        filters: dict[str, Any] | None = None,
        reranker: Any = None,
    ) -> list[SearchResult]:
        """Hybrid search with optional cross-encoder reranking."""
        candidates = self.hybrid_search(query, n=n * 4, filters=filters)
        if reranker is not None:
            return reranker.rerank(query, candidates, top_k=n)
        return candidates[:n]

    # ------------------------------------------------------------------
    # Conversation context
    # ------------------------------------------------------------------

    def get_conversation_context(self, conv_uuid: str) -> list[dict[str, Any]]:
        """Load the full conversation from SQLite for display.

        Args:
            conv_uuid: The conversation UUID.

        Returns:
            List of message dicts ordered by position.
        """
        return self.db.get_conversation_messages(conv_uuid)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_chroma_where(filters: dict[str, Any]) -> dict[str, Any] | None:
        """Convert user-facing filters to a ChromaDB where clause."""
        conditions: list[dict[str, Any]] = []
        if "source_id" in filters:
            conditions.append({"source_id": filters["source_id"]})
        if "sender" in filters:
            conditions.append({"sender": filters["sender"]})
        if "date_from" in filters:
            conditions.append({"date": {"$gte": filters["date_from"]}})
        if "date_to" in filters:
            conditions.append({"date": {"$lte": filters["date_to"]}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    @staticmethod
    def _parse_chroma_results(raw: dict[str, Any]) -> list[SearchResult]:
        """Convert raw ChromaDB query results into SearchResult objects."""
        results: list[SearchResult] = []
        if not raw or not raw.get("ids") or not raw["ids"][0]:
            return results

        ids = raw["ids"][0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            text = documents[i] if i < len(documents) else ""

            results.append(SearchResult(
                conversation_uuid=meta.get("conversation_uuid", ""),
                message_uuid=meta.get("message_uuid", doc_id),
                conversation_name=meta.get("conversation_name", ""),
                text=text,
                score=distance,
                source_id=meta.get("source_id", ""),
                sender=meta.get("sender", ""),
                created_at=meta.get("date", ""),
            ))
        return results
