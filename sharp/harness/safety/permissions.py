"""Permission manager - tool risk classification."""

from __future__ import annotations

from sharp.harness.core.types import RiskLevel
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class PermissionManager:
    """Manages tool permissions based on risk levels."""

    def __init__(
        self,
        require_approval_for: list[RiskLevel] | None = None,
        blocked_tools: list[str] | None = None,
    ) -> None:
        self.require_approval_for = require_approval_for or [
            RiskLevel.EXECUTE,
            RiskLevel.CRITICAL,
        ]
        self.blocked_tools = blocked_tools or []
        self._approved_tools: set[str] = set()

    def check_permission(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        requires_approval: bool = False,
    ) -> dict[str, bool | str]:
        """Check if a tool call is permitted.

        Returns:
            dict with 'allowed' bool and 'reason' string.
        """
        # Check if blocked
        if tool_name in self.blocked_tools:
            return {"allowed": False, "reason": f"Tool '{tool_name}' is blocked"}

        # Check if approval required
        if risk_level in self.require_approval_for and requires_approval:
            if tool_name not in self._approved_tools:
                return {
                    "allowed": False,
                    "reason": f"Tool '{tool_name}' requires approval (risk: {risk_level.value})",
                }

        return {"allowed": True, "reason": "OK"}

    def approve_tool(self, tool_name: str) -> None:
        """Approve a tool for execution."""
        self._approved_tools.add(tool_name)
        logger.info(f"Tool '{tool_name}' approved")

    def revoke_approval(self, tool_name: str) -> None:
        """Revoke approval for a tool."""
        self._approved_tools.discard(tool_name)

    def is_approved(self, tool_name: str) -> bool:
        """Check if a tool has been approved."""
        return tool_name in self._approved_tools
