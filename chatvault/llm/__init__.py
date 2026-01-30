"""LLM backend registry."""
from chatvault.llm.base import BaseLLM
from chatvault.llm.ollama import OllamaLLM
from chatvault.llm.claude import ClaudeLLM


def get_available_backends() -> list[BaseLLM]:
    """Return list of available (configured) LLM backends."""
    backends = [OllamaLLM(), ClaudeLLM()]
    return [b for b in backends if b.is_available()]


def get_backend(name: str) -> BaseLLM:
    """Get a specific backend by name."""
    backends = {"ollama": OllamaLLM, "claude": ClaudeLLM}
    if name not in backends:
        raise ValueError(f"Unknown backend: {name}. Available: {list(backends.keys())}")
    return backends[name]()
