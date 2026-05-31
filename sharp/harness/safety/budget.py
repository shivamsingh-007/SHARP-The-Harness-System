"""Budget manager - cost and token limits."""

from __future__ import annotations

from sharp.harness.core.config import SafetyConfig
from sharp.harness.core.errors import BudgetExceededError
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class BudgetManager:
    """Manages token and cost budgets.

    Prevents runaway costs by tracking usage and enforcing limits.
    """

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config
        self._total_tokens = 0
        self._total_cost = 0.0
        self._session_tokens = 0
        self._session_cost = 0.0

    def check(self) -> None:
        """Check if budget limits are exceeded.

        Raises:
            BudgetExceededError: If budget is exceeded.
        """
        if not self.config.budget_enabled:
            return

        if self._session_cost >= self.config.max_cost_usd:
            raise BudgetExceededError(
                budget_type="cost",
                limit=self.config.max_cost_usd,
                actual=self._session_cost,
            )

        if self._session_tokens >= self.config.max_tokens:
            raise BudgetExceededError(
                budget_type="tokens",
                limit=self.config.max_tokens,
                actual=self._session_tokens,
            )

    def record_tokens(self, count: int) -> None:
        """Record token usage."""
        self._total_tokens += count
        self._session_tokens += count
        logger.debug(f"Tokens used: {count} (session: {self._session_tokens})")

    def record_cost(self, amount: float) -> None:
        """Record cost."""
        self._total_cost += amount
        self._session_cost += amount
        logger.debug(f"Cost: ${amount:.4f} (session: ${self._session_cost:.4f})")

    def reset_session(self) -> None:
        """Reset session budget tracking."""
        self._session_tokens = 0
        self._session_cost = 0.0

    def get_usage(self) -> dict[str, float]:
        """Get current budget usage."""
        return {
            "session_tokens": self._session_tokens,
            "session_cost": self._session_cost,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "token_limit": self.config.max_tokens,
            "cost_limit": self.config.max_cost_usd,
            "token_usage_pct": (self._session_tokens / self.config.max_tokens * 100)
            if self.config.max_tokens > 0
            else 0,
            "cost_usage_pct": (self._session_cost / self.config.max_cost_usd * 100)
            if self.config.max_cost_usd > 0
            else 0,
        }
