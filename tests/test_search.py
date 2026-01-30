"""Tests for search module — keyword search and RRF logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chatvault.search import SearchEngine, SearchResult


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_defaults(self) -> None:
        r = SearchResult(
            conversation_uuid="c1",
            message_uuid="m1",
            conversation_name="Test",
            text="hello",
            score=0.5,
        )
        assert r.source_id == ""
        assert r.sender == ""
        assert r.created_at == ""


class TestKeywordSearch:
    """Tests for FTS5 keyword search."""

    def test_keyword_search_returns_results(self, populated_db) -> None:
        engine = SearchEngine.__new__(SearchEngine)
        engine.db = populated_db
        engine.engine = MagicMock()
        results = engine.keyword_search("investment", n=5)
        assert len(results) > 0
        assert any("investment" in r.text.lower() for r in results)

    def test_keyword_search_empty_query(self, populated_db) -> None:
        engine = SearchEngine.__new__(SearchEngine)
        engine.db = populated_db
        engine.engine = MagicMock()
        results = engine.keyword_search("", n=5)
        assert results == []

    def test_keyword_search_no_match(self, populated_db) -> None:
        engine = SearchEngine.__new__(SearchEngine)
        engine.db = populated_db
        engine.engine = MagicMock()
        results = engine.keyword_search("xyznonexistent", n=5)
        assert results == []


class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion logic."""

    def test_rrf_combines_results(self) -> None:
        """RRF should merge semantic and keyword results."""
        engine = SearchEngine.__new__(SearchEngine)

        semantic = [
            SearchResult("c1", "m1", "Conv1", "text1", 0.1),
            SearchResult("c2", "m2", "Conv2", "text2", 0.2),
        ]
        keyword = [
            SearchResult("c2", "m2", "Conv2", "text2", 0.0),
            SearchResult("c3", "m3", "Conv3", "text3", 0.0),
        ]

        with patch.object(engine, "semantic_search", return_value=semantic):
            with patch.object(engine, "keyword_search", return_value=keyword):
                results = engine.hybrid_search("test", n=10)

        uuids = [r.message_uuid for r in results]
        assert "m2" in uuids  # appears in both, should be ranked high
        assert len(results) == 3

    def test_rrf_score_ordering(self) -> None:
        """Items in both lists should score higher than single-list items."""
        engine = SearchEngine.__new__(SearchEngine)

        shared = SearchResult("c1", "m1", "Conv", "text", 0.1)
        only_semantic = SearchResult("c2", "m2", "Conv2", "text2", 0.2)
        only_keyword = SearchResult("c3", "m3", "Conv3", "text3", 0.0)

        with patch.object(engine, "semantic_search", return_value=[shared, only_semantic]):
            with patch.object(engine, "keyword_search", return_value=[shared, only_keyword]):
                results = engine.hybrid_search("test", n=10)

        # Shared result should be first (highest RRF score)
        assert results[0].message_uuid == "m1"


class TestParseChromaResults:
    """Tests for _parse_chroma_results static method."""

    def test_empty_results(self) -> None:
        assert SearchEngine._parse_chroma_results({}) == []
        assert SearchEngine._parse_chroma_results(None) == []

    def test_valid_results(self) -> None:
        raw = {
            "ids": [["id1", "id2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [[
                {"conversation_uuid": "c1", "message_uuid": "m1", "conversation_name": "Conv1"},
                {"conversation_uuid": "c2", "message_uuid": "m2", "conversation_name": "Conv2"},
            ]],
            "distances": [[0.1, 0.5]],
        }
        results = SearchEngine._parse_chroma_results(raw)
        assert len(results) == 2
        assert results[0].score == 0.1
        assert results[1].conversation_name == "Conv2"


class TestBuildChromaWhere:
    """Tests for _build_chroma_where static method."""

    def test_no_filters(self) -> None:
        assert SearchEngine._build_chroma_where({}) is None

    def test_single_filter(self) -> None:
        result = SearchEngine._build_chroma_where({"source_id": "claude"})
        assert result == {"source_id": "claude"}

    def test_multiple_filters(self) -> None:
        result = SearchEngine._build_chroma_where({
            "source_id": "claude",
            "sender": "human",
        })
        assert "$and" in result
        assert len(result["$and"]) == 2

    def test_date_filters(self) -> None:
        result = SearchEngine._build_chroma_where({
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        })
        assert "$and" in result
