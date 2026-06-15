"""LLM integration tests — real Ollama via LiteLLM.

IMPORTANT: These tests require a running Ollama instance with llama3.1:8b.
By default, CI runs only mocked tests. These are gated behind the
``llm_integration`` pytest marker.

Run with:
    pytest tests/test_llm_integration.py -v -m llm_integration

What these tests verify:
    - Shape and coarse correctness of LLM output (not exact wording)
    - That the full engine pipeline works end-to-end with a real LLM
    - That tool calling, state isolation, and orchestrator routing work

What these tests do NOT verify:
    - Exact response content (LLMs are non-deterministic)
    - Production performance (local Ollama is slower than cloud APIs)
    - Multi-turn conversation quality
    - Complex reasoning chains
"""

from __future__ import annotations

import pytest

from sharp import HarnessEngine, HarnessConfig


# ---------------------------------------------------------------------------
# Approval-style tests: check shape and coarse correctness only.
# These are the tests you'd run before merging a PR that touches the engine.
# ---------------------------------------------------------------------------


@pytest.mark.llm_integration
class TestApprovalBasics:
    """Approval-style tests: verify the engine produces plausible output."""

    def setup_method(self) -> None:
        self.config = HarnessConfig.ollama()
        self.config.execution.max_iterations = 5

    @pytest.mark.asyncio
    async def test_math_answer_is_numeric(self) -> None:
        """3*7 should produce a response containing 21."""
        engine = HarnessEngine(self.config)
        result = await engine.run("What is 3*7? Reply with just the number.")

        assert result.success, f"Engine failed: {result}"
        # Coarse correctness: output must contain the right number
        assert "21" in result.output, f"Expected '21' in output: {result.output}"
        # Shape checks
        assert result.total_tokens > 0
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_time_answer_mentions_utc(self) -> None:
        """Time query should produce output mentioning UTC."""
        engine = HarnessEngine(self.config)
        result = await engine.run("What time is it in UTC?")

        assert result.success, f"Engine failed: {result}"
        assert "UTC" in result.output.upper(), f"Expected 'UTC' in output: {result.output}"
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_simple_addition(self) -> None:
        """2+2 should produce 4."""
        engine = HarnessEngine(self.config)
        result = await engine.run("What is 2+2? Reply with just the number.")

        assert result.success, f"Engine failed: {result}"
        assert "4" in result.output, f"Expected '4' in output: {result.output}"
        assert result.total_tokens > 0

    @pytest.mark.asyncio
    async def test_output_is_nonempty_string(self) -> None:
        """Any reasonable prompt should produce a non-empty string output."""
        engine = HarnessEngine(self.config)
        result = await engine.run("Say hello.")

        assert result.success, f"Engine failed: {result}"
        assert isinstance(result.output, str)
        assert len(result.output) > 0


# ---------------------------------------------------------------------------
# Tool-calling tests: verify the engine can invoke built-in tools.
# ---------------------------------------------------------------------------


@pytest.mark.llm_integration
class TestApprovalToolCalling:
    """Verify tool calling works end-to-end with real LLM."""

    def setup_method(self) -> None:
        self.config = HarnessConfig.ollama()
        self.config.execution.max_iterations = 5

    @pytest.mark.asyncio
    async def test_calculate_tool_returns_correct_result(self) -> None:
        """Model should call calculate(12*17) and return 204."""
        engine = HarnessEngine(self.config)
        result = await engine.run("Use the calculate tool to compute 12 * 17")

        assert result.success, f"Engine failed: {result}"
        assert "204" in result.output, f"Expected '204' in output: {result.output}"
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_file_listing_tool_invoked(self) -> None:
        """Model should call list_directory and return a file listing."""
        engine = HarnessEngine(self.config)
        result = await engine.run("List the files in the current directory")

        assert result.success, f"Engine failed: {result}"
        # Output should be substantial (not just a one-word answer)
        assert len(result.output) > 10, f"Output too short: {result.output}"
        assert result.total_latency_ms > 0


# ---------------------------------------------------------------------------
# State isolation: multiple sequential calls on the same engine.
# ---------------------------------------------------------------------------


@pytest.mark.llm_integration
class TestApprovalStateIsolation:
    """Verify sequential calls don't leak state."""

    def setup_method(self) -> None:
        self.config = HarnessConfig.ollama()
        self.config.execution.max_iterations = 5

    @pytest.mark.asyncio
    async def test_sequential_math_calls(self) -> None:
        """5+3=8, then 10-4=6 — state should not leak between calls."""
        engine = HarnessEngine(self.config)

        r1 = await engine.run("What is 5 + 3?")
        assert r1.success, f"First call failed: {r1}"
        assert "8" in r1.output, f"Expected '8' in first output: {r1.output}"

        r2 = await engine.run("What is 10 - 4?")
        assert r2.success, f"Second call failed: {r2}"
        assert "6" in r2.output, f"Expected '6' in second output: {r2.output}"


# ---------------------------------------------------------------------------
# Orchestrator integration: verify routing + execution pipeline.
# ---------------------------------------------------------------------------


@pytest.mark.llm_integration
class TestApprovalOrchestrator:
    """Approval-style tests for the Orchestrator with real LLM."""

    def setup_method(self) -> None:
        from sharp.harness.orchestration.orchestrator import Orchestrator, OrchestratorConfig

        self.config = HarnessConfig.ollama()
        self.config.execution.max_iterations = 5
        self.orchestrator_config = OrchestratorConfig(
            engine_config=self.config,
            max_retries=1,
        )
        self.orchestrator = Orchestrator(config=self.orchestrator_config)

    @pytest.mark.asyncio
    async def test_orchestrator_returns_output(self) -> None:
        """Orchestrator should produce non-empty output for a simple request."""
        result = await self.orchestrator.handle_request(
            raw_request={"message": "What is 2+2?"},
            interface_type="custom_api",
        )

        assert result.output, f"Orchestrator returned empty output: {result}"
        assert len(result.output) > 0
        assert result.audit_entry is not None

    @pytest.mark.asyncio
    async def test_orchestrator_audit_logged(self) -> None:
        """Orchestrator should populate audit log after request."""
        await self.orchestrator.handle_request(
            raw_request={"message": "Say hello"},
            interface_type="custom_api",
        )

        summary = self.orchestrator.audit.get_summary()
        assert summary["total_entries"] >= 1

    @pytest.mark.asyncio
    async def test_orchestrator_performance_tracked(self) -> None:
        """Orchestrator should update performance tracker."""
        await self.orchestrator.handle_request(
            raw_request={"message": "What is 5*5?"},
            interface_type="custom_api",
        )

        snapshot = self.orchestrator.performance.get_snapshot()
        assert snapshot["total_responses"] >= 1
