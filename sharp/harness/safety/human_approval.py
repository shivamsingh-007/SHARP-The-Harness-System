"""Human-in-the-loop approval gates."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class HumanApprovalGate:
    """Human-in-the-loop approval gate.

    Pauses execution and waits for human approval before proceeding.
    """

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self._approval_callback: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None

    def set_approval_callback(
        self, callback: Callable[[str, dict[str, Any]], Awaitable[bool]]
    ) -> None:
        """Set a callback function for approval requests."""
        self._approval_callback = callback

    async def request_approval(
        self,
        tool_name: str,
        context: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> bool:
        """Request human approval for a tool execution.

        Args:
            tool_name: Name of the tool requiring approval.
            context: Additional context about what will be executed.
            timeout: Maximum time to wait for approval.

        Returns:
            True if approved, False if rejected.
        """
        logger.info(f"Approval requested for tool: {tool_name}")

        # Use callback if set
        if self._approval_callback:
            try:
                return await asyncio.wait_for(
                    self._approval_callback(tool_name, context or {}),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Approval timeout for tool: {tool_name}")
                return False

        # Default: approve (for non-interactive environments)
        logger.info(f"Auto-approving tool: {tool_name} (no callback set)")
        return True

    def approve(self, request_id: str) -> None:
        """Approve a pending request."""
        if request_id in self._pending:
            self._pending[request_id].set_result(True)

    def reject(self, request_id: str) -> None:
        """Reject a pending request."""
        if request_id in self._pending:
            self._pending[request_id].set_result(False)

    def get_pending(self) -> list[str]:
        """Get list of pending approval requests."""
        return list(self._pending.keys())
