"""Tests for RAG pipeline."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chatvault.rag import RAGPipeline, RAGResponse, SYSTEM_PROMPT
from chatvault.search import SearchResult
from tests.conftest import MockLLM


class TestRAGPipeline:
    """Tests for the RAG pipeline."""

    def _make_pipeline(self) -> RAGPipeline:
        """Create a pipeline with mocked dependencies."""
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.search = MagicMock()
        pipeline.llm = MockLLM()
        pipeline.reranker = None
        return pipeline

    def test_query_returns_rag_response(self) -> None:
        pipeline = self._make_pipeline()
        pipeline.search.hybrid_search.return_value = [
            SearchResult("c1", "m1", "Test Conv", "Some context text", 0.5,
                         created_at="2025-03-10"),
        ]
        response = pipeline.query("What is investment?")
        assert isinstance(response, RAGResponse)
        assert "Mock answer" in response.answer
        assert len(response.sources) == 1

    def test_query_with_chat_history(self) -> None:
        pipeline = self._make_pipeline()
        pipeline.search.hybrid_search.return_value = []
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        response = pipeline.query("Follow up question", chat_history=history)
        assert isinstance(response, RAGResponse)

    def test_build_context_with_results(self) -> None:
        results = [
            SearchResult("c1", "m1", "Conv1", "text1", 0.5, created_at="2025-01-01"),
            SearchResult("c2", "m2", "Conv2", "text2", 0.3),
        ]
        context = RAGPipeline._build_context(results)
        assert "[1]" in context
        assert "[2]" in context
        assert "Conv1" in context
        assert "2025-01-01" in context

    def test_build_context_empty(self) -> None:
        context = RAGPipeline._build_context([])
        assert "No relevant context" in context

    def test_build_context_truncates_long_text(self) -> None:
        results = [
            SearchResult("c1", "m1", "Conv", "x" * 5000, 0.5),
        ]
        context = RAGPipeline._build_context(results)
        # Context should truncate text to 1500 chars
        assert len(context) < 5000

    def test_system_prompt_content(self) -> None:
        assert "knowledge assistant" in SYSTEM_PROMPT
        assert "cite" in SYSTEM_PROMPT.lower()

    def test_get_system_prompt(self) -> None:
        assert RAGPipeline._get_system_prompt() == SYSTEM_PROMPT
