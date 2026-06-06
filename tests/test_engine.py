"""Tests for core/engine.py run() path."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sharp.harness.core.engine import HarnessEngine
from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.types import RiskLevel, HarnessResult


class TestHarnessEngineInit:
    def test_init_default(self):
        engine = HarnessEngine()
        assert engine.config is not None
        assert engine._trace_id is not None

    def test_init_custom_config(self):
        config = HarnessConfig()
        config.llm.model = "gpt-4o-mini"
        engine = HarnessEngine(config)
        assert engine.config.llm.model == "gpt-4o-mini"

    def test_init_creates_all_zones(self):
        engine = HarnessEngine()
        assert engine.context_curator is not None
        assert engine.prompt_composer is not None
        assert engine.tool_registry is not None
        assert engine.execution_loop is not None
        assert engine.subagent_manager is not None
        assert engine.validator is not None
        assert engine.retry_engine is not None
        assert engine.circuit_breaker is not None
        assert engine.budget_manager is not None
        assert engine.checkpoint_manager is not None
        assert engine.metrics is not None

    def test_subagents_registered_by_default(self):
        engine = HarnessEngine()
        agents = engine.subagent_manager.list_agents()
        names = [a.name for a in agents]
        assert "researcher" in names
        assert "coder" in names
        assert "reviewer" in names


class TestHarnessEngineMemory:
    def test_add_memory(self):
        engine = HarnessEngine()
        engine.add_memory("key", "value")
        assert engine._memory["key"] == "value"

    def test_add_multiple_memory(self):
        engine = HarnessEngine()
        engine.add_memory("k1", "v1")
        engine.add_memory("k2", "v2")
        assert len(engine._memory) == 2


class TestHarnessEngineToolRegistration:
    def test_tool_registration(self):
        engine = HarnessEngine()
        initial_count = len(engine._tools)

        @engine.tool(risk_level=RiskLevel.READ)
        async def test_tool(x: str) -> str:
            """Test tool."""
            return x

        assert len(engine._tools) == initial_count + 1
        assert engine._tools[-1].name == "test_tool"

    def test_multiple_tools(self):
        engine = HarnessEngine()
        initial_count = len(engine._tools)

        @engine.tool()
        async def tool_a() -> str:
            """Tool A."""
            return "a"

        @engine.tool()
        async def tool_b() -> str:
            """Tool B."""
            return "b"

        assert len(engine._tools) == initial_count + 2


class TestHarnessEngineRun:
    @pytest.mark.asyncio
    async def test_run_simple_request(self, mock_llm_provider):
        """Test the full run() pipeline with mocked LLM."""
        config = HarnessConfig.default()
        config.validation.llm_judge_enabled = False
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_llm_provider):
            result = await engine.run("What is 2 + 2?")

        assert isinstance(result, HarnessResult)
        assert result.success is True
        assert "Mock response" in result.output
        assert result.total_tokens > 0

    @pytest.mark.asyncio
    async def test_run_with_memory(self, mock_llm_provider):
        """Test run() with pre-loaded memory."""
        config = HarnessConfig.default()
        config.validation.llm_judge_enabled = False
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)
        engine.add_memory("context", "Important background info")

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_llm_provider):
            result = await engine.run("Tell me about the context")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_records_metrics(self, mock_llm_provider):
        """Test that run() records metrics."""
        config = HarnessConfig.default()
        config.validation.llm_judge_enabled = False
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_llm_provider):
            await engine.run("Test metrics")

        aggregate = engine.metrics.get_aggregate()
        assert aggregate["total_traces"] >= 1

    @pytest.mark.asyncio
    async def test_run_stores_prior_output(self, mock_llm_provider):
        """Test that run() stores output for future context."""
        config = HarnessConfig.default()
        config.validation.llm_judge_enabled = False
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_llm_provider):
            await engine.run("First request")

        assert len(engine._prior_outputs) == 1
        assert "Mock response" in engine._prior_outputs[0]

    @pytest.mark.asyncio
    async def test_run_circuit_breaker_open(self):
        """Test that run() respects circuit breaker."""
        config = HarnessConfig.default()
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)

        # Trip the circuit breaker
        for _ in range(config.safety.failure_threshold + 1):
            engine.circuit_breaker.record_failure()

        result = await engine.run("Should fail")
        assert result.success is False
        assert "Circuit breaker" in result.error or "circuit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_budget_exceeded(self):
        """Test that run() respects budget limits."""
        config = HarnessConfig.default()
        config.safety.max_tokens = 1
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)
        engine.budget_manager.record_tokens(100)

        result = await engine.run("Should fail")
        assert result.success is False


class TestHarnessEngineDelegate:
    @pytest.mark.asyncio
    async def test_delegate_to_subagent(self, mock_llm_provider):
        """Test sub-agent delegation."""
        config = HarnessConfig.default()
        config.mcp.enabled = False
        config.mcp.auto_discover = False
        engine = HarnessEngine(config)

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_llm_provider):
            result = await engine.delegate_to_subagent("researcher", "Find info about X")

        assert isinstance(result, str)
        assert len(result) > 0


class TestHarnessEngineContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager usage."""
        config = HarnessConfig.default()
        config.mcp.enabled = False

        async with HarnessEngine(config) as engine:
            assert engine is not None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test close method."""
        config = HarnessConfig.default()
        config.mcp.enabled = False
        engine = HarnessEngine(config)
        await engine.close()  # Should not raise
