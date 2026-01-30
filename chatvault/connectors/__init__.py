"""Connector auto-discovery registry."""
from chatvault.connectors.base import BaseConnector, IngestResult
from chatvault.connectors.claude import ClaudeConnector

# Registry of all available connectors
CONNECTORS: list[BaseConnector] = [
    ClaudeConnector(),
]

__all__ = ["BaseConnector", "IngestResult", "ClaudeConnector", "CONNECTORS", "get_connectors"]


def get_connectors() -> list[BaseConnector]:
    """Return all registered connectors."""
    return CONNECTORS
