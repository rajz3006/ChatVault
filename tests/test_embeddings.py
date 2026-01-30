"""Tests for embeddings module — chunking logic (no ChromaDB dependency)."""
from __future__ import annotations

import pytest

from chatvault.embeddings import chunk_text, MAX_CHUNK_CHARS, CHUNK_OVERLAP


class TestChunkText:
    """Tests for the chunk_text helper."""

    def test_short_text_single_chunk(self) -> None:
        text = "Short text"
        chunks = chunk_text(text)
        assert chunks == [text]

    def test_exact_max_single_chunk(self) -> None:
        text = "a" * MAX_CHUNK_CHARS
        chunks = chunk_text(text)
        assert len(chunks) == 1

    def test_long_text_splits(self) -> None:
        text = "a" * (MAX_CHUNK_CHARS + 100)
        chunks = chunk_text(text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP)
        assert len(chunks) >= 2

    def test_overlap_content(self) -> None:
        text = "abcdefghij" * 200  # 2000 chars
        chunks = chunk_text(text, max_chars=500, overlap=100)
        # The end of chunk[0] should overlap with start of chunk[1]
        assert chunks[0][-100:] == chunks[1][:100]

    def test_all_text_covered(self) -> None:
        text = "x" * 5000
        chunks = chunk_text(text, max_chars=1000, overlap=200)
        # Reconstruct: first chunk fully, then non-overlapping parts
        reconstructed = chunks[0]
        for c in chunks[1:]:
            reconstructed += c[200:]  # skip overlap
        assert len(reconstructed) >= len(text)

    def test_empty_text(self) -> None:
        assert chunk_text("") == [""]

    def test_custom_params(self) -> None:
        text = "hello world " * 100
        chunks = chunk_text(text, max_chars=100, overlap=20)
        for c in chunks:
            assert len(c) <= 100
