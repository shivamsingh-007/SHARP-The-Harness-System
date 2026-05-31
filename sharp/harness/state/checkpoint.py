"""Checkpoint manager - save/resume on crash."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from sharp.harness.core.config import StateConfig
from sharp.harness.state.persistence import FileBackend, RedisBackend
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Checkpoint:
    """Saved state checkpoint."""

    trace_id: str
    timestamp: str
    context: list[dict[str, Any]] = field(default_factory=list)
    output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """Manages checkpoints for crash recovery."""

    def __init__(self, config: StateConfig) -> None:
        self.config = config
        if config.backend == "redis" and config.redis_url:
            self._backend = RedisBackend(config.redis_url)
        else:
            self._backend = FileBackend(config.checkpoint_dir)

    def save(
        self,
        trace_id: str,
        context: Any = None,
        output: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save a checkpoint."""
        if not self.config.enabled:
            return

        checkpoint = Checkpoint(
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=[asdict(c) for c in context] if hasattr(context, "__iter__") else [],
            output=output,
            metadata=metadata or {},
        )

        try:
            data = json.dumps(asdict(checkpoint), ensure_ascii=False)
            self._backend.set(f"checkpoint:{trace_id}", data)
            logger.debug(f"Checkpoint saved: {trace_id}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def load(self, trace_id: str) -> Checkpoint | None:
        """Load a checkpoint by trace ID."""
        if not self.config.enabled:
            return None

        try:
            data = self._backend.get(f"checkpoint:{trace_id}")
            if data:
                raw = json.loads(data)
                return Checkpoint(**raw)
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")

        return None

    def list_checkpoints(self) -> list[str]:
        """List all checkpoint trace IDs."""
        return self._backend.list_keys("checkpoint:")

    def delete(self, trace_id: str) -> bool:
        """Delete a checkpoint."""
        return self._backend.delete(f"checkpoint:{trace_id}")
