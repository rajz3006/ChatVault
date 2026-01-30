"""Tests for security hardening module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from chatvault.security import (
    check_cloud_sync,
    check_ollama_binding,
    check_api_key_safety,
    suggest_cleanup,
    run_security_audit,
)


class TestCloudSync:
    """Tests for cloud sync detection."""

    def test_safe_path(self, tmp_path: Path) -> None:
        warnings = check_cloud_sync(tmp_path)
        assert warnings == []

    def test_icloud_path(self) -> None:
        path = Path("/Users/test/Library/Mobile Documents/project")
        warnings = check_cloud_sync(path)
        assert len(warnings) == 1
        assert "iCloud" in warnings[0]

    def test_dropbox_path(self) -> None:
        path = Path("/Users/test/Dropbox/project")
        warnings = check_cloud_sync(path)
        assert len(warnings) == 1
        assert "Dropbox" in warnings[0]


class TestOllamaBinding:
    """Tests for Ollama binding check."""

    def test_localhost_safe(self) -> None:
        assert check_ollama_binding("http://localhost:11434") == []

    def test_127_safe(self) -> None:
        assert check_ollama_binding("http://127.0.0.1:11434") == []

    def test_remote_host_warning(self) -> None:
        warnings = check_ollama_binding("http://192.168.1.100:11434")
        assert len(warnings) == 1
        assert "not localhost" in warnings[0]

    def test_public_host_warning(self) -> None:
        warnings = check_ollama_binding("http://0.0.0.0:11434")
        assert len(warnings) == 1


class TestApiKeySafety:
    """Tests for API key safety scanning."""

    def test_clean_project(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text(".env\n")
        warnings = check_api_key_safety(tmp_path)
        assert warnings == []

    def test_env_not_in_gitignore(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test")
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        warnings = check_api_key_safety(tmp_path)
        assert any(".env" in w for w in warnings)

    def test_hardcoded_key_in_python(self, tmp_path: Path) -> None:
        py_file = tmp_path / "config.py"
        py_file.write_text('ANTHROPIC_API_KEY = "sk-ant-1234567890abcdef"')
        warnings = check_api_key_safety(tmp_path)
        assert any("hardcoded" in w.lower() for w in warnings)

    def test_no_env_no_gitignore(self, tmp_path: Path) -> None:
        warnings = check_api_key_safety(tmp_path)
        assert warnings == []


class TestSuggestCleanup:
    """Tests for raw export cleanup suggestions."""

    def test_no_json_files(self, tmp_path: Path) -> None:
        suggestions = suggest_cleanup(tmp_path)
        assert suggestions == []

    def test_json_files_found(self, tmp_path: Path) -> None:
        (tmp_path / "conversations.json").write_text("[]")
        suggestions = suggest_cleanup(tmp_path)
        assert len(suggestions) > 0

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        suggestions = suggest_cleanup(tmp_path / "nonexistent")
        assert suggestions == []


class TestSecurityAudit:
    """Tests for the full security audit runner."""

    def test_audit_returns_all_checks(self, tmp_path: Path) -> None:
        with patch("chatvault.security.check_disk_encryption", return_value=[]):
            results = run_security_audit(tmp_path)
        assert "cloud_sync" in results
        assert "ollama_binding" in results
        assert "api_key_safety" in results
        assert "disk_encryption" in results
        assert "raw_export_cleanup" in results
