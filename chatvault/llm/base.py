"""Base LLM interface for all backends."""
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """All LLM backends implement this interface."""

    name: str

    @abstractmethod
    def generate(self, system: str, messages: list[dict], context: str = "") -> str:
        """Generate a response given system prompt, message history, and optional context."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is currently available."""
