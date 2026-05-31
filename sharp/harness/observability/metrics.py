"""Metrics collector - cost, latency, tokens."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sharp.harness.core.config import ObservabilityConfig
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


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
    ) -> None:
        """End tracking a trace."""
        if trace_id not in self._traces:
            return

        trace = self._traces[trace_id]
        trace.end_time = time.time()
        trace.latency_ms = latency_ms or (trace.end_time - trace.start_time) * 1000
        trace.success = success
        trace.tokens_used = tokens
        trace.cost_usd = cost

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
