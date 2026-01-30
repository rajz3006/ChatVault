"""Tests for connector framework and Claude connector."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatvault.connectors.base import BaseConnector, IngestResult
from chatvault.connectors.claude import ClaudeConnector
from chatvault.connectors import get_connectors, CONNECTORS
from chatvault.db import Database


class TestClaudeConnectorDetect:
    """Tests for ClaudeConnector.detect()."""

    def test_detect_valid_export(self, claude_export_dir: Path) -> None:
        connector = ClaudeConnector()
        assert connector.detect(claude_export_dir) is True

    def test_detect_empty_dir(self, tmp_path: Path) -> None:
        connector = ClaudeConnector()
        assert connector.detect(tmp_path) is False

    def test_detect_wrong_json(self, tmp_path: Path) -> None:
        (tmp_path / "conversations.json").write_text('[{"no_chat_messages": true}]')
        connector = ClaudeConnector()
        assert connector.detect(tmp_path) is False

    def test_detect_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "conversations.json").write_text("not json at all")
        connector = ClaudeConnector()
        assert connector.detect(tmp_path) is False

    def test_detect_empty_list(self, tmp_path: Path) -> None:
        (tmp_path / "conversations.json").write_text("[]")
        connector = ClaudeConnector()
        assert connector.detect(tmp_path) is False


class TestClaudeConnectorIngest:
    """Tests for ClaudeConnector.ingest()."""

    def test_ingest_counts(self, db: Database, claude_export_dir: Path) -> None:
        connector = ClaudeConnector()
        result = connector.ingest(claude_export_dir, db)
        assert result.conversations == 3
        assert result.messages == 10
        assert result.source_id == "claude"

    def test_ingest_extras(self, db: Database, claude_export_dir: Path) -> None:
        connector = ClaudeConnector()
        result = connector.ingest(claude_export_dir, db)
        assert result.extras.get("projects") == 1
        assert result.extras.get("memories") == 1

    def test_ingest_deduplication(self, db: Database, claude_export_dir: Path) -> None:
        connector = ClaudeConnector()
        connector.ingest(claude_export_dir, db)
        connector.ingest(claude_export_dir, db)
        # Upsert should not duplicate
        assert db.get_conversation_count() == 3
        assert db.get_message_count() == 10

    def test_ingest_message_content(self, populated_db: Database) -> None:
        messages = populated_db.get_conversation_messages("conv-aaa-111")
        assert len(messages) == 4
        assert messages[0]["sender"] == "human"
        assert "investment" in messages[0]["text"].lower()

    def test_ingest_sender_normalization(self, populated_db: Database) -> None:
        messages = populated_db.get_conversation_messages("conv-bbb-222")
        senders = {m["sender"] for m in messages}
        assert senders == {"human", "assistant"}

    def test_ingest_no_conversations_file(self, db: Database, tmp_path: Path) -> None:
        """Ingest should raise when conversations.json is missing."""
        with pytest.raises(FileNotFoundError):
            ClaudeConnector().ingest(tmp_path, db)

    def test_ingest_skips_unknown_senders(self, db: Database, tmp_path: Path) -> None:
        convs = [{
            "uuid": "conv-x",
            "name": "test",
            "chat_messages": [
                {"uuid": "m1", "sender": "system", "content": [{"type": "text", "text": "hi"}]},
                {"uuid": "m2", "sender": "human", "content": [{"type": "text", "text": "hello"}]},
            ],
        }]
        (tmp_path / "conversations.json").write_text(json.dumps(convs))
        result = ClaudeConnector().ingest(tmp_path, db)
        assert result.messages == 1  # system sender skipped

    def test_extract_text_fallback(self) -> None:
        msg = {"text": "fallback text"}
        assert ClaudeConnector._extract_text(msg) == "fallback text"

    def test_extract_text_content_blocks(self) -> None:
        msg = {"content": [{"type": "text", "text": "block text"}]}
        assert ClaudeConnector._extract_text(msg) == "block text"

    def test_extract_text_no_text(self) -> None:
        msg = {"content": [{"type": "image"}]}
        assert ClaudeConnector._extract_text(msg) is None


class TestConnectorRegistry:
    """Tests for connector auto-discovery."""

    def test_registry_has_claude(self) -> None:
        assert any(isinstance(c, ClaudeConnector) for c in CONNECTORS)

    def test_get_connectors_returns_list(self) -> None:
        connectors = get_connectors()
        assert isinstance(connectors, list)
        assert len(connectors) >= 1

    def test_export_instructions(self) -> None:
        instructions = ClaudeConnector().get_export_instructions()
        assert "claude.ai" in instructions.lower()
