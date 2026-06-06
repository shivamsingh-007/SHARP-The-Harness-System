"""Tests for execution/providers.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sharp.harness.execution.providers import LLMProvider
from sharp.harness.core.config import LLMConfig
from sharp.harness.core.types import LLMResponse, ToolDefinition, RiskLevel
from sharp.harness.core.errors import ProviderError


class TestLLMProviderInit:
    def test_init_default(self):
        config = LLMConfig()
        provider = LLMProvider(config)
        assert provider.config is config

    def test_init_with_api_key(self):
        config = LLMConfig(api_key="test-key")
        provider = LLMProvider(config)
        assert provider.config.api_key == "test-key"


class TestLLMProviderComplete:
    @pytest.mark.asyncio
    async def test_complete_basic(self):
        """Test basic completion without tools."""
        config = LLMConfig(provider="openai", model="gpt-4o-mini")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, world!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        with patch("sharp.harness.execution.providers.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            provider = LLMProvider(config)
            result = await provider.complete(
                system_prompt="You are helpful.",
                user_message="Hi!",
            )

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.tokens_used == 15
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_complete_with_tools(self):
        """Test completion with tool definitions."""
        config = LLMConfig(provider="openai", model="gpt-4o-mini")

        mock_tc = MagicMock()
        mock_tc.id = "call_1"
        mock_tc.function = MagicMock()
        mock_tc.function.name = "search"
        mock_tc.function.arguments = '{"query": "test"}'

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tc]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 10

        tools = [
            ToolDefinition(
                name="search",
                description="Search the web",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
                risk_level=RiskLevel.READ,
            )
        ]

        with patch("sharp.harness.execution.providers.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            provider = LLMProvider(config)
            result = await provider.complete(
                system_prompt="You have tools.",
                user_message="Search for X",
                tools=tools,
            )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"
        assert result.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_complete_error_handling(self):
        """Test that provider errors are wrapped correctly."""
        config = LLMConfig(provider="openai", model="gpt-4o-mini")

        with patch("sharp.harness.execution.providers.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=Exception("API error"))
            provider = LLMProvider(config)

            with pytest.raises(ProviderError):
                await provider.complete(
                    system_prompt="test",
                    user_message="test",
                )


class TestLLMProviderCostEstimation:
    def test_estimate_cost_gpt4o(self):
        config = LLMConfig()
        provider = LLMProvider(config)
        cost = provider._estimate_cost("gpt-4o", 1000, 500)
        assert cost > 0

    def test_estimate_cost_gpt4o_mini(self):
        config = LLMConfig()
        provider = LLMProvider(config)
        cost = provider._estimate_cost("gpt-4o-mini", 1000, 500)
        assert cost > 0

    def test_estimate_cost_unknown_model(self):
        config = LLMConfig()
        provider = LLMProvider(config)
        cost = provider._estimate_cost("unknown-model", 1000, 500)
        assert cost > 0


class TestLLMProviderToolConversion:
    def test_tool_to_openai(self):
        config = LLMConfig()
        provider = LLMProvider(config)
        tool = ToolDefinition(
            name="test",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        result = provider._tool_to_openai(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "test"
        assert result["function"]["description"] == "A test tool"
