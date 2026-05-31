"""Tests for utilities."""

import pytest
from sharp.harness.utils.tokens import count_tokens, truncate_to_tokens
from sharp.harness.utils.format import format_tool_result, format_signal
from sharp.harness.core.types import ToolResult


class TestTokens:
    def test_count_tokens(self):
        count = count_tokens("Hello world")
        assert count > 0

    def test_truncate_to_tokens(self):
        text = "x" * 1000
        result = truncate_to_tokens(text, 10)
        assert len(result) < len(text)


class TestFormat:
    def test_format_tool_result_success(self):
        result = ToolResult(
            tool_name="test",
            success=True,
            output="result",
            duration_ms=100,
        )
        formatted = format_tool_result(result)
        assert "test" in formatted
        assert "✓" in formatted

    def test_format_tool_result_failure(self):
        result = ToolResult(
            tool_name="test",
            success=False,
            output="",
            error="failed",
        )
        formatted = format_tool_result(result)
        assert "✗" in formatted

    def test_format_signal(self):
        formatted = format_signal("error", "Something went wrong", "Try again")
        assert "harness:signal" in formatted
        assert "Something went wrong" in formatted
