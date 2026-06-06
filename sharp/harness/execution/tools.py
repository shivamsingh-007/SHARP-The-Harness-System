"""Tool registry - governance, risk levels, execution."""

from __future__ import annotations

from typing import Any, Callable, Awaitable

from sharp.harness.core.config import ToolConfig
from sharp.harness.core.errors import ToolError
from sharp.harness.core.types import RiskLevel, ToolDefinition, ToolResult
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Registry and governance layer for tools.

    Features:
    - Risk level classification
    - Schema validation
    - Output truncation
    - Audit trail
    """

    def __init__(self, config: ToolConfig) -> None:
        self.config = config
        self._tools: dict[str, tuple[Callable[..., Awaitable[Any]], ToolDefinition]] = {}
        self._execution_history: list[ToolResult] = []

    def register(self, func: Callable[..., Awaitable[Any]], definition: ToolDefinition) -> None:
        """Register a tool with its definition."""
        if definition.name in self.config.blocked_tools:
            logger.warning(f"Tool '{definition.name}' is blocked, skipping registration")
            return

        self._tools[definition.name] = (func, definition)
        logger.info(f"Registered tool: {definition.name} (risk: {definition.risk_level.value})")

    def get(self, name: str) -> tuple[Callable[..., Awaitable[Any]], ToolDefinition] | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return [defn for _, defn in self._tools.values()]

    def check_permission(self, tool_name: str) -> bool:
        """Check if a tool call is allowed based on risk level."""
        tool = self._tools.get(tool_name)
        if not tool:
            return False

        _, definition = tool

        # Check if blocked
        if tool_name in self.config.blocked_tools:
            return False

        # Check risk level permissions
        if definition.risk_level in self.config.require_approval_for:
            if definition.requires_approval:
                logger.info(f"Tool '{tool_name}' requires approval")
                # In production, this would trigger HITL
                return True  # For now, allow

        return True

    def _check_blocked_commands(self, arguments: dict[str, Any]) -> str | None:
        """Check if any argument contains a blocked command pattern.

        Returns:
            The blocked command pattern if found, else None.
        """
        for blocked in self.config.blocked_tools:
            for key, value in arguments.items():
                if isinstance(value, str) and blocked in value:
                    return blocked
        return None

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool with governance checks."""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found",
            )

        func, definition = tool

        # Check for blocked commands in arguments
        blocked = self._check_blocked_commands(arguments)
        if blocked:
            logger.warning(f"Blocked command detected: '{blocked}' in tool '{tool_name}'")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Blocked command '{blocked}' is not allowed",
            )

        # Permission check
        if not self.check_permission(tool_name):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Permission denied for tool '{tool_name}'",
            )

        # Execute with timeout
        import asyncio
        start_time = __import__("time").time()

        try:
            result = await asyncio.wait_for(
                func(**arguments),
                timeout=definition.timeout,
            )
            elapsed_ms = (__import__("time").time() - start_time) * 1000

            # Truncate output if needed
            output = str(result)
            if len(output) > self.config.max_output_tokens * 4:  # Rough char estimate
                output = output[: self.config.max_output_tokens * 4] + "\n... [truncated]"

            tool_result = ToolResult(
                tool_name=tool_name,
                success=True,
                output=output,
                duration_ms=elapsed_ms,
            )

        except asyncio.TimeoutError:
            elapsed_ms = (__import__("time").time() - start_time) * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Tool '{tool_name}' timed out after {definition.timeout}s",
                duration_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (__import__("time").time() - start_time) * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=str(e),
                duration_ms=elapsed_ms,
            )

        self._execution_history.append(tool_result)
        return tool_result

    def get_history(self) -> list[ToolResult]:
        """Get tool execution history."""
        return self._execution_history.copy()
