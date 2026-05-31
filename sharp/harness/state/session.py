"""Session manager - session lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Session:
    """A harness session."""

    session_id: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_ids: list[str] = field(default_factory=list)


class SessionManager:
    """Manages session lifecycle."""

    def __init__(self, ttl: int = 3600) -> None:
        self.ttl = ttl
        self._sessions: dict[str, Session] = {}

    def create(self, metadata: dict[str, Any] | None = None) -> Session:
        """Create a new session."""
        session = Session(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        logger.info(f"Session created: {session.session_id}")
        return session

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def add_trace(self, session_id: str, trace_id: str) -> None:
        """Add a trace ID to a session."""
        session = self._sessions.get(session_id)
        if session:
            session.trace_ids.append(trace_id)

    def list_active(self) -> list[Session]:
        """List all active sessions."""
        return list(self._sessions.values())

    def close(self, session_id: str) -> None:
        """Close a session."""
        self._sessions.pop(session_id, None)
        logger.info(f"Session closed: {session_id}")
