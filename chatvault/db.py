"""Universal SQLite schema and database helpers for ChatVault."""
import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite database wrapper with universal schema for chat history."""

    def __init__(self, db_path: str | Path = "chatvault.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.init_schema()

    def init_schema(self) -> None:
        """Create core tables and FTS5 virtual table if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_path TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversations (
                uuid TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES sources(id),
                name TEXT,
                summary TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                uuid TEXT PRIMARY KEY,
                conversation_uuid TEXT NOT NULL REFERENCES conversations(uuid),
                position INTEGER NOT NULL,
                sender TEXT NOT NULL CHECK(sender IN ('human', 'assistant')),
                text TEXT,
                created_at TEXT,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_uuid, position);

            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                text, conversation_name, summary
            );

            CREATE TABLE IF NOT EXISTS attachments (
                uuid TEXT PRIMARY KEY,
                message_uuid TEXT REFERENCES messages(uuid),
                type TEXT,
                filename TEXT,
                mime_type TEXT,
                content BLOB,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_tags (
                conversation_uuid TEXT REFERENCES conversations(uuid),
                tag_id INTEGER REFERENCES tags(id),
                PRIMARY KEY (conversation_uuid, tag_id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                answer TEXT,
                chunk_ids TEXT,
                rating INTEGER CHECK(rating IN (-1, 1)),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Add starred column (ALTER TABLE IF NOT EXISTS not supported in SQLite)
        try:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN starred INTEGER DEFAULT 0")
            self.conn.commit()
        except Exception:
            self.conn.rollback()  # Release any implicit transaction lock
        self.conn.commit()

    def drop_all(self) -> None:
        """Drop all tables for a fresh start."""
        self.conn.executescript("""
            DROP TABLE IF EXISTS conversation_tags;
            DROP TABLE IF EXISTS tags;
            DROP TABLE IF EXISTS messages_fts;
            DROP TABLE IF EXISTS feedback;
            DROP TABLE IF EXISTS attachments;
            DROP TABLE IF EXISTS messages;
            DROP TABLE IF EXISTS conversations;
            DROP TABLE IF EXISTS sources;
        """)
        self.conn.commit()

    def upsert_source(self, id: str, name: str, file_path: str | None = None) -> None:
        """Insert or replace a source record."""
        self.conn.execute(
            "INSERT OR REPLACE INTO sources (id, name, file_path) VALUES (?, ?, ?)",
            (id, name, file_path),
        )
        self.conn.commit()

    def upsert_conversation(
        self,
        uuid: str,
        source_id: str,
        name: str | None = None,
        summary: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace a conversation record."""
        self.conn.execute(
            """INSERT OR REPLACE INTO conversations
               (uuid, source_id, name, summary, created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uuid, source_id, name, summary, created_at, updated_at,
             json.dumps(metadata or {})),
        )

    def upsert_message(
        self,
        uuid: str,
        conversation_uuid: str,
        position: int,
        sender: str,
        text: str | None = None,
        created_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace a message record."""
        self.conn.execute(
            """INSERT OR REPLACE INTO messages
               (uuid, conversation_uuid, position, sender, text, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uuid, conversation_uuid, position, sender, text, created_at,
             json.dumps(metadata or {})),
        )

    def upsert_attachment(
        self,
        uuid: str,
        message_uuid: str,
        type: str,
        filename: str | None = None,
        mime_type: str | None = None,
        content: bytes | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace an attachment record."""
        self.conn.execute(
            "INSERT OR REPLACE INTO attachments (uuid, message_uuid, type, filename, mime_type, content, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid, message_uuid, type, filename, mime_type, content, json.dumps(metadata or {})),
        )

    def get_message_attachments(self, message_uuid: str) -> list[dict[str, Any]]:
        """Return all attachments for a message."""
        rows = self.conn.execute(
            "SELECT * FROM attachments WHERE message_uuid = ?", (message_uuid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def commit(self) -> None:
        """Commit the current transaction."""
        self.conn.commit()

    def rebuild_fts(self) -> None:
        """Rebuild the FTS5 index from messages + conversation data."""
        self.conn.execute("DELETE FROM messages_fts")
        self.conn.execute("""
            INSERT INTO messages_fts (rowid, text, conversation_name, summary)
            SELECT m.rowid, m.text, c.name, c.summary
            FROM messages m
            JOIN conversations c ON m.conversation_uuid = c.uuid
            WHERE m.text IS NOT NULL AND m.text != ''
        """)
        self.conn.commit()

    def get_all_conversations(self) -> list[dict[str, Any]]:
        """Return all conversations as a list of dicts."""
        rows = self.conn.execute(
            "SELECT * FROM conversations ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_conversation_messages(self, conv_uuid: str) -> list[dict[str, Any]]:
        """Return all messages for a conversation, ordered by position."""
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE conversation_uuid = ? ORDER BY position",
            (conv_uuid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_message_count(self) -> int:
        """Return total message count."""
        return self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    def get_conversation_count(self) -> int:
        """Return total conversation count."""
        return self.conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]

    def get_stats(self) -> list[dict[str, Any]]:
        """Return counts per source."""
        rows = self.conn.execute("""
            SELECT s.id, s.name,
                   COUNT(DISTINCT c.uuid) AS conversations,
                   COUNT(m.uuid) AS messages
            FROM sources s
            LEFT JOIN conversations c ON c.source_id = s.id
            LEFT JOIN messages m ON m.conversation_uuid = c.uuid
            GROUP BY s.id, s.name
        """).fetchall()
        return [dict(r) for r in rows]

    def create_tag(self, name: str) -> int:
        cur = self.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def get_tags(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def tag_conversation(self, conv_uuid: str, tag_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO conversation_tags (conversation_uuid, tag_id) VALUES (?, ?)",
            (conv_uuid, tag_id)
        )
        self.conn.commit()

    def untag_conversation(self, conv_uuid: str, tag_id: int) -> None:
        self.conn.execute(
            "DELETE FROM conversation_tags WHERE conversation_uuid = ? AND tag_id = ?",
            (conv_uuid, tag_id)
        )
        self.conn.commit()

    def get_conversation_tags(self, conv_uuid: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT t.* FROM tags t JOIN conversation_tags ct ON t.id = ct.tag_id WHERE ct.conversation_uuid = ?",
            (conv_uuid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def toggle_star(self, conv_uuid: str) -> bool:
        current = self.conn.execute(
            "SELECT starred FROM conversations WHERE uuid = ?", (conv_uuid,)
        ).fetchone()
        new_val = 0 if (current and current["starred"]) else 1
        self.conn.execute(
            "UPDATE conversations SET starred = ? WHERE uuid = ?", (new_val, conv_uuid)
        )
        self.conn.commit()
        return bool(new_val)

    def get_starred_conversations(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM conversations WHERE starred = 1 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_conversations_by_tag(self, tag_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT c.* FROM conversations c JOIN conversation_tags ct ON c.uuid = ct.conversation_uuid WHERE ct.tag_id = ? ORDER BY c.created_at DESC",
            (tag_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_feedback(self, query: str, answer: str | None, chunk_ids: list[str] | None, rating: int) -> None:
        """Insert a feedback record for a RAG response."""
        self.conn.execute(
            "INSERT INTO feedback (query, answer, chunk_ids, rating) VALUES (?, ?, ?, ?)",
            (query, answer, json.dumps(chunk_ids or []), rating),
        )
        self.conn.commit()

    def get_feedback_stats(self) -> dict[int, int]:
        """Return feedback counts grouped by rating."""
        rows = self.conn.execute(
            "SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating"
        ).fetchall()
        return {r["rating"]: r["count"] for r in rows}

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
