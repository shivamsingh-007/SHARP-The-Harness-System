"""Custom exceptions for the harness system."""

from __future__ import annotations


class HarnessError(Exception):
    """Base exception for all harness errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ContextError(HarnessError):
    """Errors in the context engineering zone."""


class PromptError(HarnessError):
    """Errors in the prompt engineering zone."""


class ExecutionError(HarnessError):
    """Errors in the LLM execution layer."""


class ValidationError(HarnessError):
    """Errors in the validation zone."""


class SafetyError(HarnessError):
    """Safety violations (circuit breaker, budget, permissions)."""


class StateError(HarnessError):
    """State persistence errors."""


class CircuitBreakerOpenError(SafetyError):
    """Circuit breaker is open - too many consecutive failures."""

    def __init__(self, failures: int, cooldown_seconds: float) -> None:
        super().__init__(
            f"Circuit breaker open after {failures} consecutive failures. "
            f"Retry after {cooldown_seconds:.1f}s."
        )
        self.failures = failures
        self.cooldown_seconds = cooldown_seconds


class BudgetExceededError(SafetyError):
    """Token or cost budget exceeded."""

    def __init__(self, budget_type: str, limit: float, actual: float) -> None:
        super().__init__(
            f"{budget_type} budget exceeded: {actual:.2f} / {limit:.2f}"
        )
        self.budget_type = budget_type
        self.limit = limit
        self.actual = actual


class RetryExhaustedError(HarnessError):
    """All retry attempts exhausted."""

    def __init__(self, max_attempts: int, last_error: str) -> None:
        super().__init__(
            f"Retry exhausted after {max_attempts} attempts. Last error: {last_error}"
        )
        self.max_attempts = max_attempts
        self.last_error = last_error


class ToolError(ExecutionError):
    """Tool execution error."""

    def __init__(self, tool_name: str, message: str, *, fix_instructions: str = "") -> None:
        super().__init__(f"Tool '{tool_name}' error: {message}")
        self.tool_name = tool_name
        self.fix_instructions = fix_instructions


class ProviderError(ExecutionError):
    """LLM provider error."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"Provider '{provider}' error: {message}")
        self.provider = provider
