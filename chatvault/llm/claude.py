"""Claude API LLM backend for ChatVault."""
from __future__ import annotations

import os

from chatvault.llm.base import BaseLLM


class ClaudeLLM(BaseLLM):
    """LLM backend using the Anthropic Claude API."""

    name: str = "claude"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    def generate(self, system: str, messages: list[dict], context: str = "") -> str:
        """Generate a response via the Anthropic SDK.

        Args:
            system: System prompt.
            messages: List of dicts with 'role' and 'content' keys.
            context: Optional RAG context injected into the system prompt.

        Returns:
            The assistant's response text.
        """
        try:
            import anthropic
        except ImportError:
            return "[Claude error] anthropic package not installed. Run: pip install anthropic"

        full_system = f"{system}\n\n### Context\n{context}" if context else system

        # Convert messages to Anthropic format (role must be 'user' or 'assistant')
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                role = "user"
            anthropic_messages.append({
                "role": role,
                "content": msg.get("content", ""),
            })

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=full_system,
                messages=anthropic_messages,
            )
            return response.content[0].text
        except Exception as e:
            return f"[Claude error] {e}"

    def is_available(self) -> bool:
        """Check if the Anthropic API key is configured."""
        return bool(self.api_key)
