"""Context curator - orchestrates select, compress, drop operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sharp.harness.core.config import ContextConfig
from sharp.harness.context.compressor import ContextCompressor
from sharp.harness.context.memory import MemoryManager
from sharp.harness.context.retrieval import DocumentRetriever
from sharp.harness.context.sources import ContextSource, ContextSourceManager
from sharp.harness.utils.tokens import count_tokens
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CuratedContext:
    """Result of context curation."""

    sources: list[ContextSource]
    total_tokens: int
    dropped: list[str] = field(default_factory=list)
    compressed: list[str] = field(default_factory=list)


class ContextCurator:
    """Curates context from multiple sources.

    Operations:
    - SELECT: Choose relevant context based on keywords/priority
    - COMPRESS: Reduce token count to fit budget
    - DROP: Remove irrelevant or redundant context
    """

    def __init__(self, config: ContextConfig) -> None:
        self.config = config
        self.compressor = ContextCompressor(
            total_budget=config.total_token_budget,
            compression_threshold=config.compression_threshold,
            dedup_threshold=config.dedup_threshold,
        )
        self.source_manager = ContextSourceManager()

    def curate(
        self,
        user_request: str,
        memory: dict[str, str] | None = None,
        prior_outputs: list[str] | None = None,
        retrieved_docs: list[dict[str, Any]] | None = None,
        checkpoint_context: list[ContextSource] | None = None,
    ) -> CuratedContext:
        """Curate context from all sources.

        1. SELECT: Gather all sources, filter by relevance
        2. DROP: Remove low-priority/irrelevant items
        3. COMPRESS: Fit within token budget
        """
        logger.info("Starting context curation")

        # Phase 1: SELECT - Gather all sources
        all_sources: list[ContextSource] = []

        # User request (highest priority)
        all_sources.append(
            ContextSource(
                name="user_request",
                content=user_request,
                source_type="user",
                priority=-1,
            )
        )

        # Memory
        if memory:
            for key, value in memory.items():
                all_sources.append(
                    ContextSource(
                        name=f"memory:{key}",
                        content=value,
                        source_type="memory",
                        priority=0,
                    )
                )

        # Prior tool outputs
        if prior_outputs:
            for i, output in enumerate(prior_outputs[-3:]):  # Last 3 outputs
                all_sources.append(
                    ContextSource(
                        name=f"prior_output:{i}",
                        content=output,
                        source_type="tool_output",
                        priority=1,
                    )
                )

        # Retrieved docs
        if retrieved_docs:
            for doc in retrieved_docs:
                all_sources.append(
                    ContextSource(
                        name=doc.get("name", "doc"),
                        content=doc.get("content", ""),
                        source_type="retrieved_doc",
                        priority=2,
                        metadata=doc.get("metadata", {}),
                    )
                )

        # Checkpoint context
        if checkpoint_context:
            all_sources.extend(checkpoint_context)

        # Phase 2: DROP - Remove irrelevant/duplicate content
        dropped = []
        filtered_sources = []

        # Filter by keywords if configured
        active_keywords = self._extract_keywords(user_request)

        for source in all_sources:
            # Drop empty content
            if not source.content.strip():
                dropped.append(f"{source.name}: empty")
                continue

            # Drop if token count is 0
            if source.token_count == 0:
                dropped.append(f"{source.name}: zero tokens")
                continue

            filtered_sources.append(source)

        # Deduplicate
        unique_contents = self.compressor.deduplicate([s.content for s in filtered_sources])
        if len(unique_contents) < len(filtered_sources):
            dropped.append(f"Dedup: {len(filtered_sources) - len(unique_contents)} items")
            seen = set()
            deduped = []
            for s in filtered_sources:
                if s.content not in seen:
                    seen.add(s.content)
                    deduped.append(s)
            filtered_sources = deduped

        # Phase 3: COMPRESS - Fit within budget
        total_tokens = sum(s.token_count for s in filtered_sources)
        compressed = []

        if total_tokens > self.config.total_token_budget:
            logger.info(
                f"Compressing context: {total_tokens} tokens > {self.config.total_token_budget} budget"
            )

            # Prioritize and compress
            sorted_sources = sorted(filtered_sources, key=lambda s: s.priority)
            remaining = self.config.total_token_budget
            final_sources = []

            for source in sorted_sources:
                if source.token_count <= remaining:
                    final_sources.append(source)
                    remaining -= source.token_count
                else:
                    # Compress to fit
                    if remaining > 200:
                        from sharp.harness.utils.tokens import truncate_to_tokens

                        truncated = truncate_to_tokens(source.content, remaining)
                        final_sources.append(
                            ContextSource(
                                name=source.name,
                                content=truncated,
                                source_type=source.source_type,
                                priority=source.priority,
                            )
                        )
                        compressed.append(source.name)
                    break

            filtered_sources = final_sources
            total_tokens = sum(s.token_count for s in filtered_sources)

        logger.info(
            f"Context curated: {len(filtered_sources)} sources, "
            f"{total_tokens} tokens, {len(dropped)} dropped, {len(compressed)} compressed"
        )

        return CuratedContext(
            sources=filtered_sources,
            total_tokens=total_tokens,
            dropped=dropped,
            compressed=compressed,
        )

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text for context filtering."""
        # Simple keyword extraction - can be enhanced with NLP
        words = text.lower().split()
        # Filter common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                     "have", "has", "had", "do", "does", "did", "will", "would", "could",
                     "should", "may", "might", "shall", "can", "need", "dare", "ought",
                     "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
                     "as", "into", "through", "during", "before", "after", "above", "below",
                     "between", "out", "off", "over", "under", "again", "further", "then",
                     "once", "here", "there", "when", "where", "why", "how", "all", "both",
                     "each", "few", "more", "most", "other", "some", "such", "no", "nor",
                     "not", "only", "own", "same", "so", "than", "too", "very", "just",
                     "don", "now"}
        return [w for w in words if w not in stopwords and len(w) > 2][:10]
