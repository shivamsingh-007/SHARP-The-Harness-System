"""Tests for observability/metrics.py - Metrics collector."""

import pytest
from sharp.harness.observability.metrics import MetricsCollector, TraceMetrics
from sharp.harness.core.config import ObservabilityConfig


class TestMetricsCollector:
    @pytest.fixture
    def collector(self):
        return MetricsCollector(ObservabilityConfig())

    def test_start_trace(self, collector):
        collector.start_trace("trace-1")
        assert "trace-1" in collector._traces

    def test_end_trace(self, collector):
        collector.start_trace("trace-1")
        collector.end_trace("trace-1", success=True, latency_ms=100.0, tokens=50, cost=0.001)
        trace = collector.get_trace("trace-1")
        assert trace is not None
        assert trace.latency_ms == 100.0
        assert trace.tokens_used == 50
        assert trace.cost_usd == 0.001
        assert trace.success is True

    def test_end_trace_nonexistent(self, collector):
        collector.end_trace("nonexistent")  # Should not raise

    def test_aggregate_metrics(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1", success=True, latency_ms=100, tokens=50, cost=0.001)
        collector.start_trace("t2")
        collector.end_trace("t2", success=False, latency_ms=200, tokens=30, cost=0.002)

        agg = collector.get_aggregate()
        assert agg["total_traces"] == 2
        assert agg["successful_traces"] == 1
        assert agg["failed_traces"] == 1
        assert agg["total_tokens"] == 80
        assert agg["total_cost"] == pytest.approx(0.003)

    def test_average_latency(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1", latency_ms=100)
        collector.start_trace("t2")
        collector.end_trace("t2", latency_ms=200)

        agg = collector.get_aggregate()
        assert agg["avg_latency_ms"] == 150.0

    def test_get_all_traces(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1")
        collector.start_trace("t2")
        collector.end_trace("t2")

        traces = collector.get_all_traces()
        assert len(traces) == 2

    def test_trace_metadata(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1", metadata={"model": "gpt-4o"})
        trace = collector.get_trace("t1")
        assert trace.metadata.get("model") == "gpt-4o"
