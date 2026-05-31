"""Tests for prompt engineering zone."""

import pytest
from sharp.harness.prompt.composer import PromptComposer
from sharp.harness.prompt.templates import PromptTemplates
from sharp.harness.prompt.budget import TokenBudget
from sharp.harness.context.sources import ContextSource
from sharp.harness.core.config import PromptConfig


class TestTokenBudget:
    def test_allocation(self):
        budget = TokenBudget(total_budget=10000, reserved_output=2000)
        report = budget.report()
        assert report["total"] == 10000
        assert report["reserved_output"] == 2000

    def test_allocate_content(self):
        budget = TokenBudget(total_budget=1000)
        content = "x" * 100000
        result = budget.allocate_for_content("context", content)
        assert len(result) < len(content)


class TestPromptTemplates:
    def test_render_default(self):
        templates = PromptTemplates()
        result = templates.render_system_prompt(
            memory="test memory",
            context="test context",
        )
        assert "test memory" in result
        assert "test context" in result

    def test_render_with_tools(self):
        from sharp.harness.core.types import ToolDefinition, RiskLevel
        templates = PromptTemplates()
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            risk_level=RiskLevel.READ,
        )
        result = templates.render_system_prompt(tools=[tool])
        assert "test_tool" in result


class TestPromptComposer:
    def test_compose_basic(self):
        config = PromptConfig()
        composer = PromptComposer(config)
        sources = [
            ContextSource(name="user", content="Hello", source_type="user"),
            ContextSource(name="memory", content="Memory content", source_type="memory"),
        ]
        result = composer.compose(user_request="Hello", context_sources=sources)
        assert result.system_prompt
        assert result.user_message == "Hello"
