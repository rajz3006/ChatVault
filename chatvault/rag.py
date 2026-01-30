"""RAG pipeline for ChatVault — retrieve context and generate answers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from chatvault.embeddings import DEFAULT_DB_PATH, DEFAULT_CHROMA_DIR
from chatvault.search import SearchEngine, SearchResult
from chatvault.llm import get_backend
from chatvault.llm.base import BaseLLM


SYSTEM_PROMPT = (
    "You are a personal knowledge assistant. You answer questions based on the "
    "user's past AI conversations. Always cite the conversation name and date "
    "when referencing specific information. If the context doesn't contain "
    "relevant information, say so honestly."
)


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""

    answer: str
    sources: list[SearchResult]


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline combining search and LLM."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        chroma_dir: str | Path = DEFAULT_CHROMA_DIR,
        llm_backend: str = "ollama",
        use_reranker: bool = False,
    ) -> None:
        """Initialise the RAG pipeline.

        Args:
            db_path: Path to the ChatVault SQLite database.
            chroma_dir: Directory for ChromaDB persistent storage.
            llm_backend: Name of the LLM backend to use ('ollama' or 'claude').
            use_reranker: Whether to use cross-encoder reranking.
        """
        self.search = SearchEngine(db_path=db_path, chroma_dir=chroma_dir)
        self.llm: BaseLLM = get_backend(llm_backend)
        self.reranker = None
        if use_reranker:
            from chatvault.reranker import Reranker
            self.reranker = Reranker()

    def query(
        self,
        user_message: str,
        chat_history: list[dict[str, str]] | None = None,
        n_results: int = 10,
    ) -> RAGResponse:
        """Retrieve relevant context and generate an answer.

        Args:
            user_message: The user's question.
            chat_history: Optional list of previous turns as dicts with 'role' and 'content'.
            n_results: Number of search results to retrieve for context.

        Returns:
            RAGResponse with the generated answer and source results.
        """
        if self.reranker is not None:
            results = self.search.reranked_search(
                user_message, n=n_results, reranker=self.reranker,
            )
        else:
            results = self.search.hybrid_search(user_message, n=n_results)
        context = self._build_context(results)

        messages: list[dict[str, str]] = []
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": user_message})

        answer = self.llm.generate(
            system=self._get_system_prompt(),
            messages=messages,
            context=context,
        )

        return RAGResponse(answer=answer, sources=results)

    @staticmethod
    def _build_context(
        results: list[SearchResult],
        max_context_tokens: int = 3000,
    ) -> str:
        """Format search results into a token-aware context string with citations.

        Adds chunks in rank order until the token budget is exhausted.
        Never truncates mid-chunk; drops lowest-ranked chunks that don't fit.

        Args:
            results: List of search results to include as context.
            max_context_tokens: Approximate max tokens for the context block.

        Returns:
            Formatted context string.
        """
        if not results:
            return "No relevant context found."

        parts: list[str] = []
        tokens_used = 0
        for i, r in enumerate(results, start=1):
            header = f"[{i}] Conversation: {r.conversation_name or 'Untitled'}"
            if r.created_at:
                try:
                    dt = datetime.fromisoformat(r.created_at.replace("Z", "+00:00"))
                    header += f" ({dt.strftime('%b %-d, %Y')})"
                except (ValueError, AttributeError):
                    header += f" ({r.created_at})"
            chunk = f"{header}\n{r.text[:1500]}"
            chunk_tokens = len(chunk) // 4
            if tokens_used + chunk_tokens > max_context_tokens:
                continue
            tokens_used += chunk_tokens
            parts.append(chunk)

        if not parts:
            return "No relevant context found."

        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _get_system_prompt() -> str:
        """Return the system prompt for RAG generation."""
        return SYSTEM_PROMPT
