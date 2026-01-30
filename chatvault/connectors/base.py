"""Base connector interface for all platform connectors."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatvault.db import Database


@dataclass
class IngestResult:
    """Result of an ingestion operation."""
    source_id: str
    conversations: int
    messages: int
    extras: dict[str, int] = field(default_factory=dict)


class BaseConnector(ABC):
    """All connectors implement this interface."""

    source_id: str
    source_name: str

    @abstractmethod
    def detect(self, data_dir: Path) -> bool:
        """Return True if this connector's export exists in data_dir."""

    @abstractmethod
    def ingest(self, data_dir: Path, db: "Database") -> IngestResult:
        """Parse export files and insert into universal schema."""

    @abstractmethod
    def get_export_instructions(self) -> str:
        """Return user-facing instructions for exporting from this platform."""
