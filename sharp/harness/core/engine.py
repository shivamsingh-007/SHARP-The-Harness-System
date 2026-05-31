"""Main HarnessEngine orchestrator - coordinates all zones."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.errors import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    RetryExhaustedError,
)
from sharp.harness.core.types import HarnessResult, ToolDefinition, ToolResult
from sharp.harness.context.curator import ContextCurator
from sharp.harness.prompt.composer import PromptComposer
from sharp.harness.execution.loop import ExecutionLoop
from sharp.harness.execution.providers import LLMProvider
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.validation.validator import ResponseValidator
from sharp.harness.validation.retry import RetryEngine
from sharp.harness.safety.circuit_breaker import CircuitBreaker
from sharp.harness.safety.budget import BudgetManager
from sharp.harness.state.checkpoint import CheckpointManager
from sharp.harness.mcp.client import MCPClient
from sharp.harness.mcp.bridge import MCPToToolBridge
from sharp.harness.observability.logging import get_logger
from sharp.harness.observability.metrics import MetricsCollector

logger = get_logger(__name__)


class HarnessEngine:
    """Main orchestrator that coordinates all harness zones.

    The engine manages the full lifecycle:
    1. Context Engineering: curate relevant context
    2. Prompt Engineering: assemble augmented prompt
    3. LLM Execution: run with tools/sub-agents
    4. Validation: check quality, retry if needed
    5. Safety: circuit breakers, budget controls
    6. State: checkpoint/resume
    7. Observability: trace, metric, log
    """

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig.default()
        self._trace_id = str(uuid.uuid4())

        # Initialize all zones
        self.context_curator = ContextCurator(self.config.context)
        self.prompt_composer = PromptComposer(self.config.prompt)
        self.tool_registry = ToolRegistry(self.config.tools)
        self.execution_loop = ExecutionLoop(self.config.execution, self.tool_registry)
        self.validator = ResponseValidator(self.config.validation)
        self.retry_engine = RetryEngine(self.config.validation)
        self.circuit_breaker = CircuitBreaker(self.config.safety)
        self.budget_manager = BudgetManager(self.config.safety)
        self.checkpoint_manager = CheckpointManager(self.config.state)
        self.metrics = MetricsCollector(self.config.observability)

        # MCP integration
        self.mcp_client = MCPClient(self.config.mcp)
        self.mcp_bridge = MCPToToolBridge(self.mcp_client, self.tool_registry)

        # State
        self._tools: list[ToolDefinition] = []
        self._memory: dict[str, str] = {}
        self._prior_outputs: list[str] = []
        self._mcp_connected = False

    def tool(
        self,
        risk_level: Any = None,
        requires_approval: bool = False,
        timeout: float = 30.0,
    ) -> Any:
        """Decorator to register a tool."""
        from sharp.harness.core.types import RiskLevel

        level = risk_level or RiskLevel.READ

        def decorator(func: Any) -> Any:
            tool_def = ToolDefinition(
                name=func.__name__,
                description=func.__doc__ or f"Tool: {func.__name__}",
                parameters={},
                risk_level=level,
                requires_approval=requires_approval,
                timeout=timeout,
            )
            self._tools.append(tool_def)
            self.tool_registry.register(func, tool_def)
            return func

        return decorator

    def add_memory(self, key: str, value: str) -> None:
        """Add an item to persistent memory."""
        self._memory[key] = value

    def load_memory_file(self, path: str) -> None:
        """Load memory from a file (like CLAUDE.md)."""
        from pathlib import Path

        content = Path(path).read_text(encoding="utf-8")
        self._memory[path] = content

    async def connect_mcp_servers(self) -> None:
        """Connect to all configured MCP servers and discover their capabilities.

        Auto-connects if mcp.auto_discover is True.
        Can be called manually for explicit control.
        """
        if not self.config.mcp.enabled:
            return

        if self._mcp_connected:
            logger.warning("MCP servers already connected")
            return

        logger.info("Connecting to MCP servers...")

        for server_config in self.config.mcp.servers:
            if not server_config.enabled:
                logger.debug(f"Skipping disabled MCP server: {server_config.name}")
                continue

            try:
                await self.mcp_client.connect_from_config(server_config)
            except Exception as e:
                logger.error(f"Failed to connect to MCP server '{server_config.name}': {e}")

        # Bridge tools into ToolRegistry
        registered_tools = await self.mcp_bridge.register_all_tools()
        self._tools.extend(registered_tools)

        # Apply risk overrides
        if self.config.mcp.tool_risk_overrides:
            await self.mcp_bridge.apply_risk_overrides(self.config.mcp.tool_risk_overrides)

        # Feed MCP resources into context
        mcp_resources = self.mcp_bridge.get_context_from_resources()
        if mcp_resources:
            for source in mcp_resources:
                self.context_curator.source_manager.add(source)

        self._mcp_connected = True
        logger.info(
            f"MCP connected: {len(self.mcp_client.connected_servers)} servers, "
            f"{len(registered_tools)} tools registered"
        )

    async def close(self) -> None:
        """Clean up MCP connections and resources."""
        if self._mcp_connected:
            await self.mcp_client.disconnect_all()
            self._mcp_connected = False
            logger.info("MCP connections closed")

    async def __aenter__(self) -> "HarnessEngine":
        """Async context manager entry."""
        if self.config.mcp.enabled and self.config.mcp.auto_discover:
            await self.connect_mcp_servers()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def run(self, user_request: str, **kwargs: Any) -> HarnessResult:
        """Execute the full harness pipeline.

        Args:
            user_request: The user's request/prompt.
            **kwargs: Additional context sources.

        Returns:
            HarnessResult with the final output and metadata.
        """
        start_time = time.time()
        self._trace_id = str(uuid.uuid4())
        self.metrics.start_trace(self._trace_id)

        try:
            # Pre-flight checks
            self.circuit_breaker.check()
            self.budget_manager.check()

            # Auto-connect MCP servers if configured
            if self.config.mcp.enabled and self.config.mcp.auto_discover and not self._mcp_connected:
                await self.connect_mcp_servers()

            # Load checkpoint if available
            checkpoint = self.checkpoint_manager.load(self._trace_id)

            # Phase 1: Context Engineering
            logger.info("Phase 1: Context Engineering")
            context_sources = self.context_curator.curate(
                user_request=user_request,
                memory=self._memory,
                prior_outputs=self._prior_outputs,
                retrieved_docs=kwargs.get("docs", []),
                checkpoint_context=checkpoint.context if checkpoint else None,
            )

            # Phase 2: Prompt Engineering
            logger.info("Phase 2: Prompt Engineering")
            augmented_prompt = self.prompt_composer.compose(
                user_request=user_request,
                context_sources=context_sources,
                tools=self._tools,
            )

            # Phase 3-4: Execution + Validation with retry
            logger.info("Phase 3-4: Execution + Validation")
            result = await self._execute_with_retry(
                augmented_prompt=augmented_prompt,
                user_request=user_request,
            )

            # Post-flight
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=True, latency_ms=elapsed_ms)
            self.circuit_breaker.record_success()
            self.budget_manager.record_tokens(result.total_tokens)
            self.budget_manager.record_cost(result.total_cost_usd)

            # Save checkpoint
            self.checkpoint_manager.save(
                self._trace_id,
                context=context_sources,
                output=result.output,
            )

            # Store output for future context
            self._prior_outputs.append(result.output)

            return HarnessResult(
                success=True,
                output=result.output,
                attempts=result.attempts,
                total_latency_ms=elapsed_ms,
                total_cost_usd=result.total_cost_usd,
                total_tokens=result.total_tokens,
                validation_score=result.validation_score,
                trace_id=self._trace_id,
            )

        except (CircuitBreakerOpenError, BudgetExceededError) as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=False, latency_ms=elapsed_ms)
            return HarnessResult(
                success=False,
                output="",
                total_latency_ms=elapsed_ms,
                error=str(e),
                trace_id=self._trace_id,
            )

        except RetryExhaustedError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=False, latency_ms=elapsed_ms)
            self.circuit_breaker.record_failure()
            return HarnessResult(
                success=False,
                output="",
                total_latency_ms=elapsed_ms,
                error=str(e),
                trace_id=self._trace_id,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=False, latency_ms=elapsed_ms)
            self.circuit_breaker.record_failure()
            logger.exception("Harness execution failed")
            return HarnessResult(
                success=False,
                output="",
                total_latency_ms=elapsed_ms,
                error=str(e),
                trace_id=self._trace_id,
            )

    async def _execute_with_retry(
        self,
        augmented_prompt: str,
        user_request: str,
    ) -> Any:
        """Execute LLM with validation retry loop."""
        max_attempts = self.config.validation.max_retries + 1
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Attempt {attempt}/{max_attempts}")

            # Execute
            provider = LLMProvider(self.config.llm)
            response = await provider.complete(
                system_prompt=augmented_prompt.system_prompt,
                user_message=augmented_prompt.user_message,
                tools=self._tools if self.config.prompt.include_tools_in_prompt else [],
            )

            # Validate
            validation = self.validator.validate(
                response=response.content,
                user_request=user_request,
                context=augmented_prompt.context_summary,
            )

            if validation.passed:
                return _ExecutionResult(
                    output=response.content,
                    attempts=attempt,
                    total_cost_usd=response.cost_usd,
                    total_tokens=response.tokens_used,
                    validation_score=validation.score,
                )

            # Record failure for retry mutation
            last_error = "; ".join(validation.issues)
            logger.warning(f"Validation failed (attempt {attempt}): {last_error}")

            # Check if we should retry
            if attempt < max_attempts:
                # Mutate context for retry
                mutated = self.retry_engine.mutate_for_retry(
                    original_prompt=augmented_prompt,
                    validation_result=validation,
                    attempt=attempt,
                )
                augmented_prompt = mutated

        raise RetryExhaustedError(max_attempts, last_error)


class _ExecutionResult:
    """Internal result from execution with retry."""

    def __init__(
        self,
        output: str,
        attempts: int,
        total_cost_usd: float,
        total_tokens: int,
        validation_score: float,
    ) -> None:
        self.output = output
        self.attempts = attempts
        self.total_cost_usd = total_cost_usd
        self.total_tokens = total_tokens
        self.validation_score = validation_score
