"""Tests for observability modules - metrics, tracing, error classification.

Covers: structured logging fields, error classification, span tracking,
metrics with error_class, telemetry context.
"""

from __future__ import annotations

import pytest
from sharp.harness.observability.metrics import (
    MetricsCollector,
    TraceMetrics,
    ErrorClass,
    classify_error,
)
from sharp.harness.observability.tracing import SpanTracker, SpanRecord
from sharp.harness.observability.telemetry import TelemetryCollector
from sharp.harness.observability.logging import get_logger
from sharp.harness.core.config import ObservabilityConfig


# ── Error Classification ─────────────────────────────────────────────────


class TestErrorClassification:
    def test_timeout_error(self):
        assert classify_error(TimeoutError("timed out")) == ErrorClass.TIMEOUT

    def test_timeout_in_message(self):
        assert classify_error(RuntimeError("connection timeout after 30s")) == ErrorClass.TIMEOUT

    def test_auth_error(self):
        assert classify_error(PermissionError("permission denied")) == ErrorClass.AUTH

    def test_auth_in_message(self):
        assert classify_error(RuntimeError("unauthorized: invalid token")) == ErrorClass.AUTH

    def test_provider_connection_error(self):
        assert classify_error(ConnectionError("connection refused")) == ErrorClass.PROVIDER

    def test_provider_in_message(self):
        assert classify_error(RuntimeError("openai rate limit exceeded")) == ErrorClass.PROVIDER

    def test_tool_error(self):
        assert classify_error(RuntimeError("tool execution failed")) == ErrorClass.TOOL

    def test_validation_error(self):
        assert classify_error(RuntimeError("validation judge returned invalid score")) == ErrorClass.VALIDATION

    def test_config_error(self):
        assert classify_error(ValueError("config missing api_key")) == ErrorClass.CONFIG

    def test_unknown_error(self):
        assert classify_error(RuntimeError("something weird happened")) == ErrorClass.UNKNOWN

    def test_value_error_with_config(self):
        assert classify_error(ValueError("config parse error")) == ErrorClass.CONFIG


# ── MetricsCollector with Error Class ────────────────────────────────────


class TestMetricsCollectorErrorClass:
    @pytest.fixture
    def collector(self):
        config = ObservabilityConfig(metrics_enabled=False)
        return MetricsCollector(config)

    def test_end_trace_with_error_class(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1", success=False, error_class=ErrorClass.PROVIDER)

        trace = collector.get_trace("t1")
        assert trace is not None
        assert trace.error_class == ErrorClass.PROVIDER

    def test_end_trace_without_error_class(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1", success=True)

        trace = collector.get_trace("t1")
        assert trace.error_class is None

    def test_aggregate_tracks_failures(self, collector):
        collector.start_trace("t1")
        collector.end_trace("t1", success=False, error_class=ErrorClass.TIMEOUT)

        collector.start_trace("t2")
        collector.end_trace("t2", success=True)

        agg = collector.get_aggregate()
        assert agg["total_traces"] == 2
        assert agg["failed_traces"] == 1
        assert agg["successful_traces"] == 1


# ── SpanTracker ──────────────────────────────────────────────────────────


class TestSpanTracker:
    def test_records_spans(self):
        tracker = SpanTracker()

        with tracker.span("engine.run", trace_id="t1"):
            pass

        spans = tracker.get_spans_for_trace("t1")
        assert len(spans) == 1
        assert spans[0].name == "engine.run"
        assert spans[0].duration_ms >= 0

    def test_parent_child_hierarchy(self):
        tracker = SpanTracker()

        with tracker.span("engine.run", trace_id="t1") as parent:
            with tracker.span("loop.execute", trace_id="t1"):
                pass

        spans = tracker.get_spans_for_trace("t1")
        assert len(spans) == 2

        outer = [s for s in spans if s.name == "engine.run"][0]
        inner = [s for s in spans if s.name == "loop.execute"][0]

        assert inner.parent_name == "engine.run"
        assert outer.parent_name is None

    def test_span_records_attributes(self):
        tracker = SpanTracker()

        with tracker.span("test", trace_id="t1", attributes={"key": "value"}):
            pass

        spans = tracker.get_spans_for_trace("t1")
        assert spans[0].attributes == {"key": "value"}

    def test_span_records_error_status(self):
        tracker = SpanTracker()

        with pytest.raises(RuntimeError):
            with tracker.span("failing", trace_id="t1"):
                raise RuntimeError("boom")

        spans = tracker.get_spans_for_trace("t1")
        assert spans[0].status == "error: RuntimeError"

    def test_get_all_spans(self):
        tracker = SpanTracker()

        with tracker.span("a", trace_id="t1"):
            pass
        with tracker.span("b", trace_id="t2"):
            pass

        all_spans = tracker.get_all_spans()
        assert len(all_spans) == 2

    def test_clear(self):
        tracker = SpanTracker()

        with tracker.span("a", trace_id="t1"):
            pass

        tracker.clear()
        assert len(tracker.get_all_spans()) == 0

    def test_empty_trace(self):
        tracker = SpanTracker()
        assert tracker.get_spans_for_trace("nonexistent") == []


# ── Telemetry with Context ──────────────────────────────────────────────


class TestTelemetryContext:
    def test_events_have_trace_id(self):
        collector = TelemetryCollector()
        collector.emit("test.event", trace_id="t1", data={"key": "value"})

        events = collector.get_events("test.event")
        assert len(events) == 1
        assert events[0].trace_id == "t1"
        assert events[0].data["key"] == "value"

    def test_filter_by_trace_id(self):
        collector = TelemetryCollector()
        collector.emit("event.a", trace_id="t1")
        collector.emit("event.b", trace_id="t2")
        collector.emit("event.c", trace_id="t1")

        events = collector.get_events(trace_id="t1")
        assert len(events) == 2

    def test_filter_by_event_type(self):
        collector = TelemetryCollector()
        collector.emit("type.a", trace_id="t1")
        collector.emit("type.b", trace_id="t1")
        collector.emit("type.a", trace_id="t2")

        events = collector.get_events(event_type="type.a")
        assert len(events) == 2

    def test_clear(self):
        collector = TelemetryCollector()
        collector.emit("event", trace_id="t1")
        collector.clear()
        assert len(collector.get_events()) == 0
