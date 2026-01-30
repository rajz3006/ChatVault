"""Shared test fixtures for ChatVault test suite."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

from chatvault.db import Database


# ---------------------------------------------------------------------------
# Minimal Claude export fixture (3 conversations, 10 messages)
# ---------------------------------------------------------------------------

SAMPLE_CONVERSATIONS = [
    {
        "uuid": "conv-aaa-111",
        "name": "Investment strategies",
        "created_at": "2025-03-10T14:30:00Z",
        "updated_at": "2025-03-10T15:00:00Z",
        "account": {"uuid": "acct-001"},
        "chat_messages": [
            {
                "uuid": "msg-001",
                "sender": "human",
                "created_at": "2025-03-10T14:30:00Z",
                "content": [{"type": "text", "text": "What are good investment strategies for beginners?"}],
            },
            {
                "uuid": "msg-002",
                "sender": "assistant",
                "created_at": "2025-03-10T14:30:30Z",
                "content": [{"type": "text", "text": "Here are some beginner investment strategies: 1) Index funds 2) Dollar cost averaging 3) Diversification across asset classes."}],
            },
            {
                "uuid": "msg-003",
                "sender": "human",
                "created_at": "2025-03-10T14:31:00Z",
                "content": [{"type": "text", "text": "Tell me more about index funds"}],
            },
            {
                "uuid": "msg-004",
                "sender": "assistant",
                "created_at": "2025-03-10T14:31:30Z",
                "content": [{"type": "text", "text": "Index funds track a market index like the S&P 500. They offer low fees and broad diversification."}],
            },
        ],
    },
    {
        "uuid": "conv-bbb-222",
        "name": "Python debugging tips",
        "created_at": "2025-04-05T10:00:00Z",
        "updated_at": "2025-04-05T10:30:00Z",
        "summary": "Discussion about Python debugging techniques",
        "account": {"uuid": "acct-001"},
        "chat_messages": [
            {
                "uuid": "msg-005",
                "sender": "human",
                "created_at": "2025-04-05T10:00:00Z",
                "content": [{"type": "text", "text": "How do I debug Python code effectively?"}],
            },
            {
                "uuid": "msg-006",
                "sender": "assistant",
                "created_at": "2025-04-05T10:00:30Z",
                "content": [{"type": "text", "text": "Use pdb, breakpoint(), logging, and IDE debuggers. Print statements work for quick checks."}],
            },
            {
                "uuid": "msg-007",
                "sender": "human",
                "created_at": "2025-04-05T10:01:00Z",
                "content": [{"type": "text", "text": "What about using pytest for testing?"}],
            },
            {
                "uuid": "msg-008",
                "sender": "assistant",
                "created_at": "2025-04-05T10:01:30Z",
                "content": [{"type": "text", "text": "pytest is excellent. Use fixtures, parametrize, and assert for clear test writing."}],
            },
        ],
    },
    {
        "uuid": "conv-ccc-333",
        "name": "Recipe ideas",
        "created_at": "2025-05-01T18:00:00Z",
        "updated_at": "2025-05-01T18:20:00Z",
        "account": {"uuid": "acct-001"},
        "chat_messages": [
            {
                "uuid": "msg-009",
                "sender": "human",
                "created_at": "2025-05-01T18:00:00Z",
                "content": [{"type": "text", "text": "Give me a quick pasta recipe"}],
            },
            {
                "uuid": "msg-010",
                "sender": "assistant",
                "created_at": "2025-05-01T18:00:30Z",
                "content": [{"type": "text", "text": "Aglio e olio: Cook spaghetti. Sauté garlic in olive oil with red pepper flakes. Toss with pasta and parsley."}],
            },
        ],
    },
]

SAMPLE_PROJECTS = [
    {"uuid": "proj-001", "name": "Personal Finance", "description": "Finance research project"},
]

SAMPLE_MEMORIES = [
    {"uuid": "mem-001", "content": "User prefers index funds"},
]


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test data."""
    return tmp_path


@pytest.fixture
def claude_export_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a minimal Claude export."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    (export_dir / "conversations.json").write_text(
        json.dumps(SAMPLE_CONVERSATIONS), encoding="utf-8"
    )
    (export_dir / "projects.json").write_text(
        json.dumps(SAMPLE_PROJECTS), encoding="utf-8"
    )
    (export_dir / "memories.json").write_text(
        json.dumps(SAMPLE_MEMORIES), encoding="utf-8"
    )
    return export_dir


@pytest.fixture
def db(tmp_path: Path) -> Generator[Database, None, None]:
    """Create an in-memory-like SQLite Database in a temp file."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def populated_db(db: Database, claude_export_dir: Path) -> Database:
    """Return a database populated with sample Claude export data."""
    from chatvault.connectors.claude import ClaudeConnector

    connector = ClaudeConnector()
    connector.ingest(claude_export_dir, db)
    db.rebuild_fts()
    return db


class MockLLM:
    """Deterministic mock LLM backend for testing."""

    name = "mock"

    def generate(self, system: str, messages: list[dict], context: str = "") -> str:
        last_msg = messages[-1]["content"] if messages else ""
        return f"Mock answer to: {last_msg}"

    def is_available(self) -> bool:
        return True
