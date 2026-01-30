"""Tests for Database schema, inserts, queries, and FTS5."""
from __future__ import annotations

from pathlib import Path

import pytest

from chatvault.db import Database


class TestSchemaCreation:
    """Tests for database schema initialisation."""

    def test_schema_idempotent(self, db: Database) -> None:
        """Calling init_schema twice should not raise."""
        db.init_schema()
        db.init_schema()

    def test_tables_exist(self, db: Database) -> None:
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "sources" in names
        assert "conversations" in names
        assert "messages" in names

    def test_fts_table_exists(self, db: Database) -> None:
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "messages_fts" in names


class TestInsertQuery:
    """Tests for upsert and query operations."""

    def test_upsert_source(self, db: Database) -> None:
        db.upsert_source("test", "Test Source")
        rows = db.conn.execute("SELECT * FROM sources").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == "test"

    def test_upsert_conversation(self, db: Database) -> None:
        db.upsert_source("s1", "Source")
        db.upsert_conversation(uuid="c1", source_id="s1", name="Test Conv")
        db.commit()
        convs = db.get_all_conversations()
        assert len(convs) == 1
        assert convs[0]["name"] == "Test Conv"

    def test_upsert_message(self, db: Database) -> None:
        db.upsert_source("s1", "Source")
        db.upsert_conversation(uuid="c1", source_id="s1", name="Conv")
        db.upsert_message(uuid="m1", conversation_uuid="c1", position=0, sender="human", text="Hello")
        db.commit()
        msgs = db.get_conversation_messages("c1")
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Hello"

    def test_upsert_replaces(self, db: Database) -> None:
        db.upsert_source("s1", "Source")
        db.upsert_conversation(uuid="c1", source_id="s1", name="Old")
        db.upsert_conversation(uuid="c1", source_id="s1", name="New")
        db.commit()
        convs = db.get_all_conversations()
        assert len(convs) == 1
        assert convs[0]["name"] == "New"

    def test_message_ordering(self, db: Database) -> None:
        db.upsert_source("s1", "Source")
        db.upsert_conversation(uuid="c1", source_id="s1")
        db.upsert_message(uuid="m2", conversation_uuid="c1", position=1, sender="assistant", text="Reply")
        db.upsert_message(uuid="m1", conversation_uuid="c1", position=0, sender="human", text="Hi")
        db.commit()
        msgs = db.get_conversation_messages("c1")
        assert msgs[0]["position"] == 0
        assert msgs[1]["position"] == 1


class TestCounts:
    """Tests for count helpers."""

    def test_counts(self, populated_db: Database) -> None:
        assert populated_db.get_conversation_count() == 3
        assert populated_db.get_message_count() == 10

    def test_stats(self, populated_db: Database) -> None:
        stats = populated_db.get_stats()
        assert len(stats) == 1
        assert stats[0]["conversations"] == 3
        assert stats[0]["messages"] == 10


class TestFTS5:
    """Tests for FTS5 full-text search."""

    def test_fts_search_match(self, populated_db: Database) -> None:
        rows = populated_db.conn.execute(
            "SELECT * FROM messages_fts WHERE messages_fts MATCH 'investment'"
        ).fetchall()
        assert len(rows) > 0

    def test_fts_search_no_match(self, populated_db: Database) -> None:
        rows = populated_db.conn.execute(
            "SELECT * FROM messages_fts WHERE messages_fts MATCH 'xyznonexistent'"
        ).fetchall()
        assert len(rows) == 0

    def test_rebuild_fts_idempotent(self, populated_db: Database) -> None:
        populated_db.rebuild_fts()
        populated_db.rebuild_fts()
        rows = populated_db.conn.execute(
            "SELECT COUNT(*) as cnt FROM messages_fts"
        ).fetchone()
        assert rows["cnt"] == 10


class TestDropAll:
    """Tests for drop_all."""

    def test_drop_and_recreate(self, populated_db: Database) -> None:
        populated_db.drop_all()
        populated_db.init_schema()
        assert populated_db.get_conversation_count() == 0
        assert populated_db.get_message_count() == 0
