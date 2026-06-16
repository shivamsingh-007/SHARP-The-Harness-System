"""Metrics collector - cost, latency, tokens, error classification."""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

from sharp.harness.core.config import ObservabilityConfig
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class ErrorClass(str, Enum):
    """Classification of errors by cause."""

    PROVIDER = "provider"
    TOOL = "tool"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    AUTH = "auth"
    CONFIG = "config"
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> ErrorClass:
    """Classify an exception into an error category.

    Uses exception type and message heuristics.
    """
    error_type = type(error).__name__.lower()
    error_msg = str(error).lower()

    # Timeout
    if "timeout" in error_type or "timeout" in error_msg:
        return ErrorClass.TIMEOUT
    if isinstance(error, TimeoutError):
        return ErrorClass.TIMEOUT

    # Auth
    if "auth" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
        return ErrorClass.AUTH
    if isinstance(error, PermissionError):
        return ErrorClass.AUTH

    # Config
    if "config" in error_msg or "missing" in error_msg and "key" in error_msg:
        return ErrorClass.CONFIG
    if isinstance(error, (ValueError, KeyError)) and "config" in error_msg:
        return ErrorClass.CONFIG

    # Provider (LLM/API errors)
    provider_keywords = ["openai", "anthropic", "litellm", "api", "rate limit", "quota", "model"]
    if any(kw in error_msg for kw in provider_keywords):
        return ErrorClass.PROVIDER
    if isinstance(error, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        return ErrorClass.PROVIDER

    # Tool
    tool_keywords = ["tool", "execution", "command", "subprocess", "file", "permission denied"]
    if any(kw in error_msg for kw in tool_keywords):
        return ErrorClass.TOOL

    # Validation
    validation_keywords = ["validation", "judge", "score", "schema", "parse"]
    if any(kw in error_msg for kw in validation_keywords):
        return ErrorClass.VALIDATION

    return ErrorClass.UNKNOWN


@dataclass
class TraceMetrics:
    """Metrics for a single trace."""

    trace_id: str
    start_time: float = 0.0
    end_time: float = 0.0
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error_class: ErrorClass | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates metrics."""

    def __init__(self, config: ObservabilityConfig) -> None:
        self.config = config
        self._traces: dict[str, TraceMetrics] = {}
        self._aggregate = {
            "total_traces": 0,
            "successful_traces": 0,
            "failed_traces": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_latency_ms": 0.0,
        }

    def start_trace(self, trace_id: str) -> None:
        """Start tracking a trace."""
        self._traces[trace_id] = TraceMetrics(
            trace_id=trace_id,
            start_time=time.time(),
        )

    def end_trace(
        self,
        trace_id: str,
        success: bool = True,
        latency_ms: float = 0.0,
        tokens: int = 0,
        cost: float = 0.0,
        error_class: ErrorClass | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End tracking a trace and record token/cost data."""
        if trace_id not in self._traces:
            return

        trace = self._traces[trace_id]
        trace.end_time = time.time()
        trace.latency_ms = latency_ms or (trace.end_time - trace.start_time) * 1000
        trace.success = success
        trace.tokens_used = tokens
        trace.cost_usd = cost
        trace.error_class = error_class
        if metadata:
            trace.metadata.update(metadata)

        # Update aggregates
        self._aggregate["total_traces"] += 1
        if success:
            self._aggregate["successful_traces"] += 1
        else:
            self._aggregate["failed_traces"] += 1
        self._aggregate["total_tokens"] += tokens
        self._aggregate["total_cost"] += cost

        # Recalculate average latency
        all_latencies = [t.latency_ms for t in self._traces.values() if t.end_time > 0]
        if all_latencies:
            self._aggregate["avg_latency_ms"] = sum(all_latencies) / len(all_latencies)

        if self.config.metrics_enabled:
            logger.info(
                f"Trace {trace_id}: {'✓' if success else '✗'} "
                f"{trace.latency_ms:.0f}ms, {tokens} tokens, ${cost:.4f}"
            )

    def get_trace(self, trace_id: str) -> TraceMetrics | None:
        """Get metrics for a specific trace."""
        return self._traces.get(trace_id)

    def get_aggregate(self) -> dict[str, Any]:
        """Get aggregate metrics."""
        return self._aggregate.copy()

    def get_all_traces(self) -> list[TraceMetrics]:
        """Get all trace metrics."""
        return list(self._traces.values())
