"""OpenTelemetry tracing (optional) and in-memory span tracker."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SpanRecord:
    """Record of a single span."""

    name: str
    trace_id: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    parent_name: str | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)


class SpanTracker:
    """In-memory span tracker that works without OpenTelemetry.

    Records span name, duration, parent-child hierarchy, and status.
    Queryable: get_spans_for_trace(trace_id).
    """

    def __init__(self) -> None:
        self._spans: list[SpanRecord] = []
        self._current_parent: str | None = None

    @contextmanager
    def span(
        self,
        name: str,
        trace_id: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> Generator[SpanRecord, None, None]:
        """Create and track a span."""
        record = SpanRecord(
            name=name,
            trace_id=trace_id,
            start_time=time.time(),
            parent_name=self._current_parent,
            attributes=attributes or {},
        )

        old_parent = self._current_parent
        self._current_parent = name

        try:
            yield record
            record.status = "ok"
        except Exception as e:
            record.status = f"error: {type(e).__name__}"
            raise
        finally:
            record.end_time = time.time()
            record.duration_ms = (record.end_time - record.start_time) * 1000
            self._spans.append(record)
            self._current_parent = old_parent

    def get_spans_for_trace(self, trace_id: str) -> list[SpanRecord]:
        """Get all spans for a given trace ID."""
        return [s for s in self._spans if s.trace_id == trace_id]

    def get_all_spans(self) -> list[SpanRecord]:
        """Get all recorded spans."""
        return list(self._spans)

    def clear(self) -> None:
        """Clear all recorded spans."""
        self._spans.clear()


class Tracer:
    """OpenTelemetry tracer wrapper.

    Provides a simple interface for creating spans.
    Falls back to no-op if OpenTelemetry is not installed.
    """

    def __init__(self, service_name: str = "harness-system") -> None:
        self.service_name = service_name
        self._tracer: Any = None
        self._init_opentelemetry()

    def _init_opentelemetry(self) -> None:
        """Initialize OpenTelemetry if available."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            provider = TracerProvider()
            provider.add_span_processor(
                __import__("opentelemetry.sdk.trace.export", fromlist=["SimpleSpanProcessor"]).SimpleSpanProcessor(
                    ConsoleSpanExporter()
                )
            )
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(self.service_name)
            logger.info("OpenTelemetry tracing initialized")
        except ImportError:
            logger.debug("OpenTelemetry not installed, using no-op tracer")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenTelemetry: {e}")

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Generator[None, None, None]:
        """Create a tracing span."""
        if self._tracer:
            with self._tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                yield
        else:
            yield
