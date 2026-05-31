"""Multi-provider LLM adapter using LiteLLM."""

from __future__ import annotations

import time
from typing import Any

import litellm

from sharp.harness.core.config import LLMConfig
from sharp.harness.core.errors import ProviderError
from sharp.harness.core.types import LLMResponse, ToolDefinition
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class LLMProvider:
    """Unified LLM provider using LiteLLM.

    Supports: OpenAI, Anthropic, Google, Azure, Ollama, and more.
    """

    def __init__(self, config: LLMConfig, mcp_client: Any | None = None) -> None:
        self.config = config
        self.mcp_client = mcp_client
        # Configure litellm
        if config.api_key:
            litellm.api_key = config.api_key
        if config.api_base:
            litellm.api_base = config.api_base

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[ToolDefinition] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a completion request to the LLM.

        Args:
            system_prompt: The system prompt.
            user_message: The user's message.
            tools: Optional tool definitions for function calling.
            **kwargs: Additional parameters to pass to the LLM.

        Returns:
            LLMResponse with the model's output.
        """
        start_time = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        call_kwargs: dict[str, Any] = {
            "model": f"{self.config.provider}/{self.config.model}"
            if "/" not in self.config.model
            else self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            **kwargs,
        }

        # Add tools if provided
        if tools:
            call_kwargs["tools"] = [self._tool_to_openai(t) for t in tools]

        try:
            response = await litellm.acompletion(**call_kwargs)
        except Exception as e:
            raise ProviderError(self.config.provider, str(e)) from e

        elapsed_ms = (time.time() - start_time) * 1000

        # Parse response
        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in choice.message.tool_calls
            ]

        # Extract usage
        usage = getattr(response, "usage", None)
        tokens_prompt = getattr(usage, "prompt_tokens", 0) or 0
        tokens_completion = getattr(usage, "completion_tokens", 0) or 0
        tokens_total = tokens_prompt + tokens_completion

        # Calculate cost (rough estimates)
        cost = self._estimate_cost(response.model, tokens_prompt, tokens_completion)

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.config.provider,
            tokens_used=tokens_total,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            cost_usd=cost,
            latency_ms=elapsed_ms,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "",
        )

    def _tool_to_openai(self, tool: ToolDefinition) -> dict[str, Any]:
        """Convert ToolDefinition to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters or {"type": "object", "properties": {}},
            },
        }

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD based on model and token counts."""
        # Rough pricing per 1M tokens (as of 2024)
        pricing: dict[str, tuple[float, float]] = {
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.00, 30.00),
            "claude-3-5-sonnet": (3.00, 15.00),
            "claude-3-haiku": (0.25, 1.25),
        }

        # Find matching model
        for model_key, (input_price, output_price) in pricing.items():
            if model_key in model.lower():
                input_cost = (prompt_tokens / 1_000_000) * input_price
                output_cost = (completion_tokens / 1_000_000) * output_price
                return round(input_cost + output_cost, 6)

        # Default estimate
        return round(
            (prompt_tokens / 1_000_000) * 2.50 + (completion_tokens / 1_000_000) * 10.00,
            6,
        )
