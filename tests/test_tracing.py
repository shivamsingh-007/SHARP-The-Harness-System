"""Tests for observability/tracing.py - Tracer."""

import pytest
from sharp.harness.observability.tracing import Tracer


class TestTracer:
    def test_init(self):
        tracer = Tracer(service_name="test")
        assert tracer.service_name == "test"

    def test_span_noop(self):
        tracer = Tracer(service_name="test")
        with tracer.span("test_span"):
            pass  # Should not raise

    def test_span_with_attributes(self):
        tracer = Tracer(service_name="test")
        with tracer.span("test_span", attributes={"key": "value"}):
            pass  # Should not raise

    def test_span_exception_handling(self):
        tracer = Tracer(service_name="test")
        with pytest.raises(ValueError, match="test error"):
            with tracer.span("test_span"):
                raise ValueError("test error")
