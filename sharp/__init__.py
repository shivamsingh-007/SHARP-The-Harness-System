"""Harness System - A production-grade harness for LLM agents."""

from sharp.harness.core.engine import HarnessEngine
from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.errors import (
    HarnessError,
    ValidationError,
    CircuitBreakerOpenError,
    BudgetExceededError,
    RetryExhaustedError,
)
from sharp.harness.orchestration.orchestrator import Orchestrator, OrchestratorConfig
from sharp.harness.orchestration.router import IntentRouter, IntentRouterConfig
from sharp.harness.orchestration.aggregator import ContextAggregator
from sharp.harness.orchestration.audit import AuditLogger
from sharp.harness.orchestration.types import InterfaceType, TaskType, ModelType

__version__ = "0.1.0"
__all__ = [
    "HarnessEngine",
    "HarnessConfig",
    "HarnessError",
    "ValidationError",
    "CircuitBreakerOpenError",
    "BudgetExceededError",
    "RetryExhaustedError",
    "Orchestrator",
    "OrchestratorConfig",
    "IntentRouter",
    "IntentRouterConfig",
    "ContextAggregator",
    "AuditLogger",
    "InterfaceType",
    "TaskType",
    "ModelType",
]
