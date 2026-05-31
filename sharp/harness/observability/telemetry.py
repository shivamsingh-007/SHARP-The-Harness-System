"""Telemetry events."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TelemetryEvent:
    """A telemetry event."""

    event_type: str
    timestamp: float = field(default_factory=time.time)
    trace_id: str = ""
    session_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class TelemetryCollector:
    """Collects and stores telemetry events."""

    def __init__(self, log_file: str | None = None) -> None:
        self._events: list[TelemetryEvent] = []
        self._log_file = Path(log_file) if log_file else None

    def emit(
        self,
        event_type: str,
        trace_id: str = "",
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Emit a telemetry event."""
        event = TelemetryEvent(
            event_type=event_type,
            trace_id=trace_id,
            data=data or {},
            metadata=kwargs,
        )
        self._events.append(event)

        # Write to file if configured
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write telemetry: {e}")

    def get_events(
        self,
        event_type: str | None = None,
        trace_id: str | None = None,
    ) -> list[TelemetryEvent]:
        """Get events with optional filtering."""
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if trace_id:
            events = [e for e in events if e.trace_id == trace_id]
        return events

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
