"""Shared test fixtures and mocking infrastructure for SHARP tests."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sharp.harness.core.config import (
    HarnessConfig,
    LLMConfig,
    ContextConfig,
    PromptConfig,
    ToolConfig,
    ValidationConfig,
    SafetyConfig,
    StateConfig,
    ObservabilityConfig,
    ExecutionConfig,
    MCPConfig,
)
from sharp.harness.core.types import (
    LLMResponse,
    ValidationResult,
    ToolDefinition,
    ToolResult,
    RiskLevel,
    LoopStrategy,
    ValidationLevel,
)
from sharp.harness.execution.providers import LLMProvider
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.execution.loop import ExecutionLoop
from sharp.harness.execution.subagents import SubAgentManager
from sharp.harness.context.retrieval import DocumentRetriever
from sharp.harness.context.memory import MemoryManager
from sharp.harness.validation.validator import ResponseValidator
from sharp.harness.validation.judge import LLMJudge
from sharp.harness.validation.retry import RetryEngine
from sharp.harness.validation.rules import RuleBasedValidator
from sharp.harness.safety.circuit_breaker import CircuitBreaker
from sharp.harness.safety.budget import BudgetManager
from sharp.harness.safety.human_approval import HumanApprovalGate
from sharp.harness.safety.permissions import PermissionManager
from sharp.harness.state.checkpoint import CheckpointManager
from sharp.harness.state.session import SessionManager
from sharp.harness.state.persistence import FileBackend
from sharp.harness.observability.metrics import MetricsCollector
from sharp.harness.observability.tracing import Tracer
from sharp.harness.observability.logging import setup_logging
from sharp.harness.utils.async_helpers import run_with_timeout, gather_with_limit, retry_async


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config() -> HarnessConfig:
    """Default harness configuration."""
    return HarnessConfig.default()


@pytest.fixture
def llm_config() -> LLMConfig:
    """LLM configuration for tests."""
    return LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.0,
        max_tokens=256,
        timeout=10.0,
    )


@pytest.fixture
def validation_config() -> ValidationConfig:
    """Validation configuration for tests."""
    return ValidationConfig(
        enabled=True,
        level=ValidationLevel.STRICT,
        llm_judge_enabled=False,
        min_score=0.7,
        max_retries=2,
    )


@pytest.fixture
def safety_config() -> SafetyConfig:
    """Safety configuration for tests."""
    return SafetyConfig(
        circuit_breaker_enabled=True,
        failure_threshold=3,
        recovery_seconds=1.0,
        budget_enabled=True,
        max_cost_usd=1.0,
        max_tokens=10000,
        blocked_commands=["rm -rf", "sudo", "mkfs"],
    )


@pytest.fixture
def state_config(tmp_path: Path) -> StateConfig:
    """State configuration using temp directory."""
    return StateConfig(
        enabled=True,
        backend="file",
        checkpoint_dir=str(tmp_path / "checkpoints"),
        session_ttl=3600,
    )


@pytest.fixture
def execution_config() -> ExecutionConfig:
    """Execution configuration for tests."""
    return ExecutionConfig(
        loop_strategy=LoopStrategy.REACT,
        max_iterations=5,
        timeout=30.0,
    )


@pytest.fixture
def mcp_config() -> MCPConfig:
    """MCP configuration for tests."""
    return MCPConfig(enabled=False, auto_discover=False, servers=[])


@pytest.fixture
def tool_config() -> ToolConfig:
    """Tool configuration for tests."""
    return ToolConfig(
        blocked_tools=["dangerous_tool", "rm -rf"],
        max_output_tokens=1000,
    )


# ---------------------------------------------------------------------------
# Component fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tool_registry(tool_config: ToolConfig) -> ToolRegistry:
    """Tool registry instance."""
    return ToolRegistry(tool_config)


@pytest.fixture
def execution_loop(execution_config: ExecutionConfig, tool_registry: ToolRegistry) -> ExecutionLoop:
    """Execution loop instance."""
    return ExecutionLoop(execution_config, tool_registry)


@pytest.fixture
def subagent_manager() -> SubAgentManager:
    """Sub-agent manager instance."""
    return SubAgentManager()


@pytest.fixture
def document_retriever() -> DocumentRetriever:
    """Document retriever instance."""
    return DocumentRetriever(max_tokens=4000)


@pytest.fixture
def memory_manager(tmp_path: Path) -> MemoryManager:
    """Memory manager with temp directory."""
    return MemoryManager(memory_dir=str(tmp_path / "memory"))


@pytest.fixture
def circuit_breaker(safety_config: SafetyConfig) -> CircuitBreaker:
    """Circuit breaker instance."""
    return CircuitBreaker(safety_config)


@pytest.fixture
def budget_manager(safety_config: SafetyConfig) -> BudgetManager:
    """Budget manager instance."""
    return BudgetManager(safety_config)


@pytest.fixture
def human_approval_gate() -> HumanApprovalGate:
    """Human approval gate instance."""
    return HumanApprovalGate()


@pytest.fixture
def permission_manager(safety_config: SafetyConfig) -> PermissionManager:
    """Permission manager instance."""
    return PermissionManager(
        blocked_tools=safety_config.blocked_commands,
    )


@pytest.fixture
def session_manager() -> SessionManager:
    """Session manager instance."""
    return SessionManager(ttl=3600)


@pytest.fixture
def metrics_collector() -> MetricsCollector:
    """Metrics collector instance."""
    return MetricsCollector(ObservabilityConfig())


@pytest.fixture
def tracer() -> Tracer:
    """Tracer instance (no-op if OTel not installed)."""
    return Tracer(service_name="test-harness")


@pytest.fixture
def rule_validator() -> RuleBasedValidator:
    """Rule-based validator instance."""
    return RuleBasedValidator()


@pytest.fixture
def retry_engine(validation_config: ValidationConfig) -> RetryEngine:
    """Retry engine instance."""
    return RetryEngine(validation_config)


@pytest.fixture
def file_backend(tmp_path: Path) -> FileBackend:
    """File persistence backend with temp directory."""
    return FileBackend(base_dir=str(tmp_path / "storage"))


# ---------------------------------------------------------------------------
# Mock LLM provider
# ---------------------------------------------------------------------------

class MockLLMProvider:
    """Mock LLM provider for testing without real API calls."""

    def __init__(
        self,
        responses: list[str] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        fail_after: int | None = None,
    ) -> None:
        self._responses = responses or ["Mock response"]
        self._tool_calls = tool_calls or []
        self._call_count = 0
        self._fail_after = fail_after
        self._calls: list[dict[str, Any]] = []

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[ToolDefinition] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Mock completion that returns predefined responses."""
        self._call_count += 1
        self._calls.append({
            "system_prompt": system_prompt,
            "user_message": user_message,
            "tools": tools,
            "kwargs": kwargs,
        })

        if self._fail_after and self._call_count > self._fail_after:
            from sharp.harness.core.errors import ProviderError
            raise ProviderError("mock", "Simulated failure")

        # Return tool call if configured
        if self._tool_calls and self._call_count <= len(self._tool_calls):
            tc = self._tool_calls[self._call_count - 1]
            return LLMResponse(
                content="",
                model="mock-model",
                provider="mock",
                tokens_used=100,
                cost_usd=0.0,
                latency_ms=10.0,
                tool_calls=[tc],
                finish_reason="tool_calls",
            )

        # Return text response
        idx = min(self._call_count - 1, len(self._responses) - 1)
        content = self._responses[idx]

        return LLMResponse(
            content=content,
            model="mock-model",
            provider="mock",
            tokens_used=len(content.split()) * 2,
            cost_usd=0.001,
            latency_ms=10.0,
            tool_calls=[],
            finish_reason="stop",
        )

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def last_call(self) -> dict[str, Any] | None:
        return self._calls[-1] if self._calls else None


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """Mock LLM provider with default responses."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_tools() -> MockLLMProvider:
    """Mock LLM provider that returns tool calls then a final answer."""
    return MockLLMProvider(
        tool_calls=[
            {"id": "call_1", "name": "test_tool", "arguments": '{"x": "test"}'},
        ],
        responses=["Final Answer: The result is test"],
    )


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Temp directories
# ---------------------------------------------------------------------------

@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    """Temporary checkpoint directory."""
    d = tmp_path / "checkpoints"
    d.mkdir()
    return d


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Temporary memory directory."""
    d = tmp_path / "memory"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tool_definition() -> ToolDefinition:
    """Sample tool definition for testing."""
    return ToolDefinition(
        name="test_tool",
        description="A test tool that echoes input",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "string", "description": "Input string"},
            },
            "required": ["x"],
        },
        risk_level=RiskLevel.READ,
    )


@pytest.fixture
def sample_context_sources() -> list:
    """Sample context sources for testing."""
    from sharp.harness.core.types import ContextSource, DisclosureLevel
    return [
        ContextSource(
            name="doc1",
            content="This is document 1 content with important information.",
            disclosure_level=DisclosureLevel.DETAIL,
        ),
        ContextSource(
            name="doc2",
            content="This is document 2 content with supplementary data.",
            disclosure_level=DisclosureLevel.INDEX,
        ),
    ]


@pytest.fixture
def sample_documents() -> list[dict[str, Any]]:
    """Sample documents for retrieval testing."""
    return [
        {"name": "readme", "content": "Project README with overview and setup instructions.", "score": 0.9},
        {"name": "api_docs", "content": "API documentation for the main endpoints.", "score": 0.8},
        {"name": "changelog", "content": "Version history and release notes.", "score": 0.5},
        {"name": "config_guide", "content": "Configuration guide for advanced settings.", "score": 0.7},
    ]


# ---------------------------------------------------------------------------
# Setup logging for tests
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Configure test logging."""
    setup_logging("DEBUG")
