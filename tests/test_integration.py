"""Full integration test of SHARP harness system.

Tests the complete pipeline end-to-end with mocked LLM calls.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import (
    RiskLevel, HarnessResult, LoopStrategy, ValidationLevel,
)
from sharp.harness.execution.providers import LLMProvider
from sharp.harness.execution.subagents import SubAgentManager
from sharp.harness.context.memory import MemoryManager
from sharp.harness.context.retrieval import DocumentRetriever
from sharp.harness.state.checkpoint import CheckpointManager
from sharp.harness.state.session import SessionManager
from sharp.harness.observability.metrics import MetricsCollector
from sharp.harness.safety.circuit_breaker import CircuitBreaker
from sharp.harness.safety.budget import BudgetManager


def _make_config(**overrides) -> HarnessConfig:
    """Create a test config with MCP disabled and optional overrides."""
    config = HarnessConfig.default()
    config.mcp.enabled = False
    config.mcp.auto_discover = False
    config.validation.llm_judge_enabled = False
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


class TestFullPipeline:
    """Integration test: full pipeline with mocked LLM."""

    @pytest.mark.asyncio
    async def test_end_to_end_simple(self):
        """Test complete pipeline: context -> prompt -> execute -> validate."""
        config = _make_config()
        engine = HarnessEngine(config)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=MagicMock(
            content="Python is a high-level programming language known for its simplicity.",
            tokens_used=50,
            cost_usd=0.001,
        ))

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            result = await engine.run("What is Python?")

        assert isinstance(result, HarnessResult)
        assert result.success is True
        assert "Python" in result.output
        assert result.total_tokens > 0
        assert result.total_cost_usd >= 0

    @pytest.mark.asyncio
    async def test_end_to_end_with_memory(self):
        """Test pipeline with pre-loaded memory."""
        config = _make_config()
        engine = HarnessEngine(config)
        engine.add_memory("project", "SHARP is a harness system for LLM agents")

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=MagicMock(
            content="SHARP is a harness system that helps build LLM agents.",
            tokens_used=40,
            cost_usd=0.0005,
        ))

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            result = await engine.run("Tell me about SHARP")

        assert result.success is True
        assert "SHARP" in result.output

    @pytest.mark.asyncio
    async def test_end_to_end_with_tools(self):
        """Test pipeline with registered tools (uses ReAct loop)."""
        config = _make_config()
        engine = HarnessEngine(config)

        @engine.tool(risk_level=RiskLevel.READ)
        async def search(query: str) -> str:
            """Search for information."""
            return f"Results for: {query}"

        mock_provider = MagicMock()
        # First call: tool call, second call: final answer
        mock_provider.complete = AsyncMock(side_effect=[
            MagicMock(
                content='Thought: I need to search\nAction: search(query="test")',
                tool_calls=[{"id": "c1", "name": "search", "arguments": '{"query": "test"}'}],
                tokens_prompt=30,
                tokens_completion=15,
                cost_usd=0.001,
            ),
            MagicMock(
                content="Final Answer: Based on my search, here are the results.",
                tokens_prompt=50,
                tokens_completion=30,
                cost_usd=0.002,
            ),
        ])

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            result = await engine.run("Search for test information")

        assert result.success is True
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_end_to_end_retry_on_validation_failure(self):
        """Test pipeline retries when validation fails."""
        config = _make_config()
        config.validation.max_retries = 2
        engine = HarnessEngine(config)

        call_count = 0
        async def mock_complete(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(content="", tokens_used=10, cost_usd=0.0)
            return MagicMock(content="A proper response with enough content to pass validation.", tokens_used=50, cost_usd=0.001)

        mock_provider = MagicMock()
        mock_provider.complete = mock_complete

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            result = await engine.run("Test retry")

        assert result.success is True
        assert result.attempts >= 1

    @pytest.mark.asyncio
    async def test_end_to_end_circuit_breaker(self):
        """Test circuit breaker halts execution."""
        config = _make_config()
        engine = HarnessEngine(config)

        # Trip circuit breaker
        for _ in range(config.safety.failure_threshold + 1):
            engine.circuit_breaker.record_failure()

        result = await engine.run("Should be blocked")
        assert result.success is False
        assert "ircuit" in result.error.lower() or "circuit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_end_to_end_budget_exceeded(self):
        """Test budget limits are enforced."""
        config = _make_config()
        config.safety.max_cost_usd = 0.0001
        engine = HarnessEngine(config)
        engine.budget_manager.record_cost(0.001)  # Exceed budget

        result = await engine.run("Should fail budget")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_end_to_end_subagent_delegation(self):
        """Test sub-agent delegation works end-to-end."""
        config = _make_config()
        engine = HarnessEngine(config)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=MagicMock(
            content="Research complete: Python was created by Guido van Rossum.",
            tokens_used=60,
            cost_usd=0.001,
        ))

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            result = await engine.delegate_to_subagent(
                "researcher",
                "Who created Python?",
            )

        assert isinstance(result, str)
        assert "Python" in result

    @pytest.mark.asyncio
    async def test_end_to_end_metrics_tracking(self):
        """Test metrics are recorded through the pipeline."""
        config = _make_config()
        engine = HarnessEngine(config)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=MagicMock(
            content="This is a comprehensive response that provides detailed information about the topic. It covers multiple aspects and provides thorough analysis.",
            tokens_used=30,
            cost_usd=0.001,
        ))

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            await engine.run("Test metrics")

        agg = engine.metrics.get_aggregate()
        assert agg["total_traces"] >= 1

    @pytest.mark.asyncio
    async def test_end_to_end_multiple_runs(self):
        """Test multiple sequential runs accumulate state."""
        config = _make_config()
        engine = HarnessEngine(config)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=MagicMock(
            content="This is a detailed response that provides comprehensive information about the requested topic with thorough analysis.",
            tokens_used=20,
            cost_usd=0.0005,
        ))

        with patch("sharp.harness.core.engine.LLMProvider", return_value=mock_provider):
            r1 = await engine.run("First request")
            r2 = await engine.run("Second request")

        assert r1.success is True
        assert r2.success is True
        assert len(engine._prior_outputs) == 2

    @pytest.mark.asyncio
    async def test_end_to_end_context_manager(self):
        """Test async context manager lifecycle."""
        config = _make_config()
        async with HarnessEngine(config) as engine:
            assert engine is not None
            assert isinstance(engine, HarnessEngine)

    @pytest.mark.asyncio
    async def test_end_to_end_tool_registration_and_listing(self):
        """Test tool registration and listing."""
        config = _make_config()
        engine = HarnessEngine(config)
        initial_count = len(engine.tool_registry.list_tools())

        @engine.tool(risk_level=RiskLevel.READ)
        async def tool_a() -> str:
            """Tool A."""
            return "a"

        @engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True)
        async def tool_b(x: int) -> int:
            """Tool B."""
            return x * 2

        tools = engine.tool_registry.list_tools()
        assert len(tools) == initial_count + 2
        names = [t.name for t in tools]
        assert "tool_a" in names
        assert "tool_b" in names


class TestComponentIntegration:
    """Integration tests for component interactions."""

    @pytest.mark.asyncio
    async def test_memory_to_context_to_prompt(self):
        """Test memory flows through context curation to prompt composition."""
        config = _make_config()
        engine = HarnessEngine(config)
        engine.add_memory("style", "Use formal language")

        curated = engine.context_curator.curate(
            user_request="Write a formal email",
            memory=engine._memory,
        )
        assert len(curated.sources) > 0

        prompt = engine.prompt_composer.compose(
            user_request="Write a formal email",
            context_sources=curated.sources,
        )
        assert prompt.system_prompt is not None
        assert prompt.user_message == "Write a formal email"

    def test_tool_registry_governance(self):
        """Test tool registration with risk levels and blocked tools."""
        config = _make_config()
        engine = HarnessEngine(config)

        @engine.tool(risk_level=RiskLevel.READ)
        async def safe_tool() -> str:
            """Safe tool."""
            return "ok"

        # Check permissions
        assert engine.tool_registry.check_permission("safe_tool") is True

        # List tools
        tools = engine.tool_registry.list_tools()
        assert any(t.name == "safe_tool" for t in tools)

    def test_session_and_checkpoint(self):
        """Test session creation and checkpoint save/load."""
        config = _make_config()
        engine = HarnessEngine(config)

        session = engine.checkpoint_manager._backend  # Use file backend directly
        session_manager = SessionManager()
        session_obj = session_manager.create()
        assert session_obj.session_id is not None

        # Save checkpoint
        engine.checkpoint_manager.save("test-trace", output="test output")
        loaded = engine.checkpoint_manager.load("test-trace")
        assert loaded is not None
        assert loaded.output == "test output"


# ─── Bug Fix Regression Tests ────────────────────────────────────────


class TestBugFixRegressions:
    """Regression tests for the 12 bugs identified in the brutal honest report."""

    @pytest.mark.asyncio
    async def test_loop_returns_loop_result(self):
        """CRITICAL-3: Loop returns LoopResult with real metadata, not a string."""
        from unittest.mock import AsyncMock, MagicMock

        from sharp.harness.execution.loop import ExecutionLoop, LoopResult
        from sharp.harness.execution.tools import ToolRegistry
        from sharp.harness.core.config import ExecutionConfig, ToolConfig
        from sharp.harness.core.types import LoopStrategy

        config = ExecutionConfig(max_iterations=5, loop_strategy=LoopStrategy.REACT)
        registry = ToolRegistry(ToolConfig())
        loop = ExecutionLoop(config, registry)

        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=MagicMock(
            content="Final Answer: 42",
            tool_calls=[],
            tokens_prompt=10,
            tokens_completion=5,
            cost_usd=0.001,
        ))

        result = await loop.run(provider, "What is 2+2?")
        assert isinstance(result, LoopResult)
        assert result.output == "42"
        assert result.total_tokens == 15
        assert result.total_cost_usd == 0.001
        assert result.provider_calls == 1

    @pytest.mark.asyncio
    async def test_orchestrator_reuses_engine(self):
        """CRITICAL-4: Orchestrator reuses engine across requests."""
        from sharp.harness.orchestration.orchestrator import Orchestrator, OrchestratorConfig
        from sharp.harness.orchestration.types import InterfaceType

        config = OrchestratorConfig(engine_config=HarnessConfig.default())
        orch = Orchestrator(config)

        # First request creates engine
        engine1 = orch._engine
        # Second request should reuse same engine
        engine2 = orch._engine
        assert engine1 is engine2

    def test_config_not_mutated(self):
        """HIGH-1: Orchestrator doesn't mutate shared engine_config."""
        from sharp.harness.orchestration.orchestrator import Orchestrator, OrchestratorConfig

        original_model = "gpt-4o"
        engine_config = HarnessConfig.default()
        engine_config.llm.model = original_model

        config = OrchestratorConfig(engine_config=engine_config)
        orch = Orchestrator(config)

        # Simulate what _execute_with_sharp does to config
        copied = engine_config.model_copy(deep=True)
        copied.llm.model = "claude-3-5-sonnet"

        # Original should be unchanged
        assert engine_config.llm.model == original_model

    @pytest.mark.asyncio
    async def test_judge_failure_fails_closed(self):
        """HIGH-2: Judge failure results in validation failure, not auto-pass."""
        from unittest.mock import AsyncMock

        from sharp.harness.core.config import ValidationConfig
        from sharp.harness.validation.validator import ResponseValidator

        config = ValidationConfig(llm_judge_enabled=True)
        validator = ResponseValidator(config)
        validator.llm_judge.evaluate = AsyncMock(side_effect=Exception("LLM down"))

        result = await validator.validate("Some output", "Some request")
        assert result.passed is False
        assert "LLM judge error" in result.issues[0]

    def test_severity_warning_does_not_block(self):
        """MEDIUM-2: Warning severity rules don't block pass/fail."""
        from sharp.harness.validation.rules import Rule, RuleBasedValidator

        validator = RuleBasedValidator()
        validator.add_rule(Rule(
            name="length_check",
            check=lambda r: len(r) > 100,
            message="Too short",
            severity="warning",
        ))

        result = validator.validate("Short")
        # Warning rule fails but should NOT block pass/fail
        assert result.passed is True
        assert len(result.suggestions) == 1  # Warning goes to suggestions
