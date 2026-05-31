"""Context compressor - token-aware compression of context."""

from __future__ import annotations

from sharp.harness.utils.tokens import count_tokens, truncate_to_tokens


class ContextCompressor:
    """Compresses context to fit within token budgets.

    Strategies:
    - Truncation: cut to fit budget
    - Summarization: use LLM to summarize (optional)
    - Deduplication: remove near-duplicate content
    """

    def __init__(
        self,
        total_budget: int = 8000,
        compression_threshold: float = 0.8,
        dedup_threshold: float = 0.85,
    ) -> None:
        self.total_budget = total_budget
        self.compression_threshold = compression_threshold
        self.dedup_threshold = dedup_threshold

    def needs_compression(self, token_count: int) -> bool:
        """Check if content needs compression."""
        return token_count > self.total_budget * self.compression_threshold

    def compress(
        self,
        content: str,
        max_tokens: int | None = None,
    ) -> str:
        """Compress content to fit within token budget."""
        budget = max_tokens or self.total_budget
        current_tokens = count_tokens(content)

        if current_tokens <= budget:
            return content

        # Strategy 1: Truncate
        return truncate_to_tokens(content, budget)

    def compress_sources(
        self,
        sources: list[dict[str, str]],
        budget: int,
    ) -> list[dict[str, str]]:
        """Compress multiple context sources to fit within budget.

        Prioritizes by source priority, fills budget from highest to lowest.
        """
        # Sort by priority (lower = higher priority)
        sorted_sources = sorted(sources, key=lambda s: s.get("priority", 0))

        result = []
        remaining_budget = budget

        for source in sorted_sources:
            content = source.get("content", "")
            tokens = count_tokens(content)

            if tokens <= remaining_budget:
                result.append(source)
                remaining_budget -= tokens
            else:
                # Partial fit - truncate
                if remaining_budget > 100:  # Minimum useful size
                    truncated = truncate_to_tokens(content, remaining_budget)
                    result.append({**source, "content": truncated, "truncated": True})
                break

        return result

    def deduplicate(self, contents: list[str]) -> list[str]:
        """Remove near-duplicate content based on character overlap."""
        if not contents:
            return contents

        unique = [contents[0]]
        for content in contents[1:]:
            is_dup = False
            for existing in unique:
                overlap = self._character_overlap(content, existing)
                if overlap > self.dedup_threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(content)
        return unique

    def _character_overlap(self, a: str, b: str) -> float:
        """Calculate character-level overlap ratio."""
        if not a or not b:
            return 0.0
        set_a = set(a.lower())
        set_b = set(b.lower())
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0
