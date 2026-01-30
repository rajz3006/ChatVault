"""Tests for the ingestion orchestrator."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from chatvault.db import Database
from chatvault.ingest import main as ingest_main


class TestIngestOrchestrator:
    """Tests for the ingestion main function."""

    def test_ingest_from_dir(self, claude_export_dir: Path, tmp_path: Path) -> None:
        """Ingest from an explicit data directory."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        # Prevent ingest_main from closing our db handle
        db.close = MagicMock()
        with patch("chatvault.ingest.Database", return_value=db):
            ingest_main(data_dir=str(claude_export_dir))
        assert db.get_conversation_count() == 3
        assert db.get_message_count() == 10
        db.conn.close()

    def test_ingest_force_mode(self, claude_export_dir: Path, tmp_path: Path) -> None:
        """Force mode should drop and recreate tables."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.close = MagicMock()
        with patch("chatvault.ingest.Database", return_value=db):
            ingest_main(data_dir=str(claude_export_dir))
            assert db.get_conversation_count() == 3
            ingest_main(data_dir=str(claude_export_dir), force=True)
            assert db.get_conversation_count() == 3
        db.conn.close()

    def test_ingest_no_data_dir(self, tmp_path: Path) -> None:
        """Should exit when no data directory exists."""
        with patch("chatvault.ingest.Database"):
            with patch("chatvault.ingest.Path") as MockPath:
                mock_base = MockPath.return_value
                mock_base.is_dir.return_value = False
                with pytest.raises(SystemExit):
                    ingest_main(data_dir=None)

    def test_ingest_no_exports_detected(self, tmp_path: Path) -> None:
        """Empty directory should produce no results."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.close = MagicMock()
        with patch("chatvault.ingest.Database", return_value=db):
            ingest_main(data_dir=str(empty_dir))
        assert db.get_conversation_count() == 0
        db.conn.close()
