"""OpenTelemetry tracing (optional)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


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
