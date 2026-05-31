"""Context sources - abstractions for different context types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sharp.harness.utils.tokens import count_tokens


@dataclass
class ContextSource:
    """A source of context information."""

    name: str
    content: str
    source_type: str  # "user", "memory", "tool_output", "retrieved_doc"
    priority: int = 0  # Lower = higher priority
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)


class ContextSourceManager:
    """Manages multiple context sources."""

    def __init__(self) -> None:
        self._sources: list[ContextSource] = []

    def add(self, source: ContextSource) -> None:
        """Add a context source."""
        self._sources.append(source)

    def add_user_request(self, request: str, priority: int = -1) -> ContextSource:
        """Add a user request as a context source."""
        source = ContextSource(
            name="user_request",
            content=request,
            source_type="user",
            priority=priority,
        )
        self.add(source)
        return source

    def add_memory(self, key: str, content: str, priority: int = 0) -> ContextSource:
        """Add a memory item as a context source."""
        source = ContextSource(
            name=f"memory:{key}",
            content=content,
            source_type="memory",
            priority=priority,
        )
        self.add(source)
        return source

    def add_tool_output(self, tool_name: str, output: str, priority: int = 1) -> ContextSource:
        """Add a tool output as a context source."""
        source = ContextSource(
            name=f"tool:{tool_name}",
            content=output,
            source_type="tool_output",
            priority=priority,
        )
        self.add(source)
        return source

    def add_retrieved_doc(self, doc_name: str, content: str, priority: int = 2) -> ContextSource:
        """Add a retrieved document as a context source."""
        source = ContextSource(
            name=f"doc:{doc_name}",
            content=content,
            source_type="retrieved_doc",
            priority=priority,
        )
        self.add(source)
        return source

    def get_sorted(self) -> list[ContextSource]:
        """Get sources sorted by priority (lowest first)."""
        return sorted(self._sources, key=lambda s: s.priority)

    def get_total_tokens(self) -> int:
        """Get total token count across all sources."""
        return sum(s.token_count for s in self._sources)

    def filter_by_keywords(self, keywords: list[str]) -> list[ContextSource]:
        """Filter sources that contain any of the given keywords."""
        if not keywords:
            return self._sources
        return [
            s for s in self._sources
            if any(kw.lower() in s.content.lower() for kw in keywords)
        ]
