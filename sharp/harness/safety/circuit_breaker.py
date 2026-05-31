"""Circuit breaker - stop runaway loops."""

from __future__ import annotations

import time

from sharp.harness.core.config import SafetyConfig
from sharp.harness.core.errors import CircuitBreakerOpenError
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for agent execution.

    States:
    - CLOSED: Normal operation, failures counted
    - OPEN: Too many failures, reject new attempts
    - HALF_OPEN: Testing recovery, allow one attempt
    """

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = "closed"  # "closed", "open", "half_open"

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        if self._state == "open" and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.recovery_seconds:
                self._state = "half_open"
        return self._state

    def check(self) -> None:
        """Check if the circuit breaker allows execution.

        Raises:
            CircuitBreakerOpenError: If circuit is open.
        """
        if not self.config.circuit_breaker_enabled:
            return

        current_state = self.state

        if current_state == "open":
            remaining = self.config.recovery_seconds - (
                time.time() - (self._last_failure_time or 0)
            )
            raise CircuitBreakerOpenError(
                failures=self._failure_count,
                cooldown_seconds=max(0, remaining),
            )

    def record_success(self) -> None:
        """Record a successful execution."""
        if self._state == "half_open":
            logger.info("Circuit breaker: recovery successful, closing")
            self._failure_count = 0
            self._state = "closed"
        elif self._state == "closed":
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed execution."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.config.failure_threshold:
            logger.warning(
                f"Circuit breaker: opening after {self._failure_count} failures"
            )
            self._state = "open"

    def reset(self) -> None:
        """Reset the circuit breaker."""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "closed"

    def get_status(self) -> dict[str, int | str | float]:
        """Get circuit breaker status."""
        return {
            "state": self.state,
            "failure_count": self._failure_count,
            "threshold": self.config.failure_threshold,
            "recovery_seconds": self.config.recovery_seconds,
        }
