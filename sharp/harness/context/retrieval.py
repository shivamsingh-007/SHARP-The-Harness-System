"""Document retriever - fetch and rank documents for context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sharp.harness.utils.tokens import count_tokens


@dataclass
class RetrievedDocument:
    """A retrieved document with relevance score."""

    name: str
    content: str
    score: float = 0.0  # Relevance score (0-1)
    metadata: dict[str, Any] | None = None

    @property
    def token_count(self) -> int:
        return count_tokens(self.content)


class DocumentRetriever:
    """Retrieves and ranks documents for context injection.

    Supports:
    - Static document lists
    - Keyword-based filtering
    - Score-based ranking
    """

    def __init__(self, max_tokens: int = 4000) -> None:
        self.max_tokens = max_tokens
        self._documents: list[RetrievedDocument] = []

    def add_document(
        self,
        name: str,
        content: str,
        score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a document to the retriever."""
        self._documents.append(
            RetrievedDocument(name=name, content=content, score=score, metadata=metadata)
        )

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """Add multiple documents."""
        for doc in documents:
            self.add_document(
                name=doc.get("name", "unnamed"),
                content=doc.get("content", ""),
                score=doc.get("score", 0.0),
                metadata=doc.get("metadata"),
            )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        keywords: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        """Retrieve top-k relevant documents.

        Uses simple keyword matching for relevance scoring.
        For production, replace with embedding-based retrieval.
        """
        scored_docs = []

        for doc in self._documents:
            score = self._calculate_relevance(query, doc, keywords)
            if score > 0:
                scored_docs.append((score, doc))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        # Return top-k within token budget
        result = []
        total_tokens = 0

        for score, doc in scored_docs[:top_k]:
            doc_tokens = doc.token_count
            if total_tokens + doc_tokens <= self.max_tokens:
                result.append(doc)
                total_tokens += doc_tokens
            else:
                break

        return result

    def _calculate_relevance(
        self,
        query: str,
        doc: RetrievedDocument,
        keywords: list[str] | None,
    ) -> float:
        """Calculate relevance score between query and document."""
        score = doc.score  # Base score

        # Keyword boost
        if keywords:
            query_lower = query.lower()
            content_lower = doc.content.lower()
            for kw in keywords:
                if kw.lower() in query_lower and kw.lower() in content_lower:
                    score += 0.2

        # Title/name match boost
        if doc.name.lower() in query.lower():
            score += 0.3

        return min(score, 1.0)

    def clear(self) -> None:
        """Clear all documents."""
        self._documents.clear()
