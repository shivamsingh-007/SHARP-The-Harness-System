"""Token counting and manipulation utilities."""

from __future__ import annotations

import tiktoken


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count the number of tokens in a text string."""
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate (1 token ≈ 4 chars)
        return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int, encoding_name: str = "cl100k_base") -> str:
    """Truncate text to a maximum number of tokens."""
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated = tokens[:max_tokens]
        return encoding.decode(truncated)
    except Exception:
        # Fallback: character-based truncation
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars]


def estimate_tokens_for_messages(messages: list[dict[str, str]], encoding_name: str = "cl100k_base") -> int:
    """Estimate total tokens for a list of chat messages."""
    total = 0
    for msg in messages:
        # Overhead for message formatting
        total += 4
        total += count_tokens(msg.get("role", ""), encoding_name)
        total += count_tokens(msg.get("content", ""), encoding_name)
    return total
