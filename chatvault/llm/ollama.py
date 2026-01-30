"""Ollama LLM backend for ChatVault."""
from __future__ import annotations

import json
import os
from typing import Generator

import requests

from chatvault.llm.base import BaseLLM


# ---------------------------------------------------------------------------
# Standalone helpers (usable without instantiating OllamaLLM)
# ---------------------------------------------------------------------------

def list_models(host: str = "http://localhost:11434") -> list[str]:
    """Return names of models installed in the Ollama instance.

    Args:
        host: Ollama API base URL.

    Returns:
        List of model name strings, e.g. ["llama3:latest", "tinyllama:latest"].
    """
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except requests.RequestException:
        return []


def pull_model(
    model_name: str,
    host: str = "http://localhost:11434",
) -> Generator[dict, None, None]:
    """Pull (download) an Ollama model with streaming progress.

    Yields dicts with at least a ``status`` key. During download layers the
    dict also contains ``completed`` and ``total`` (bytes) for progress
    tracking.

    Args:
        model_name: Model to pull, e.g. "llama3" or "tinyllama".
        host: Ollama API base URL.

    Yields:
        Progress dicts from the Ollama ``/api/pull`` streaming endpoint.
    """
    resp = requests.post(
        f"{host}/api/pull",
        json={"name": model_name, "stream": True},
        stream=True,
        timeout=600,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if line:
            yield json.loads(line)


class OllamaLLM(BaseLLM):
    """LLM backend using a local Ollama instance."""

    name: str = "ollama"

    def __init__(self) -> None:
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "") or self._detect_model()

    def _detect_model(self) -> str:
        """Auto-detect first available Ollama model, fallback to 'llama3'."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if models:
                    return models[0]["name"]
        except requests.RequestException:
            pass
        return "llama3"

    def generate(self, system: str, messages: list[dict], context: str = "") -> str:
        """Generate a response via Ollama's /api/chat endpoint.

        Args:
            system: System prompt.
            messages: List of dicts with 'role' and 'content' keys.
            context: Optional RAG context injected into the system prompt.

        Returns:
            The assistant's response text.
        """
        full_system = f"{system}\n\n### Context\n{context}" if context else system

        ollama_messages = [{"role": "system", "content": full_system}]
        for msg in messages:
            ollama_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": ollama_messages,
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except requests.RequestException as e:
            return f"[Ollama error] {e}"

    def is_available(self) -> bool:
        """Check if Ollama is running by hitting /api/tags."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False
