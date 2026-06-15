"""Data types for durable artifacts (feature_list.json, progress.txt)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Feature:
    """A single feature check in feature_list.json.

    Attributes:
        id: Unique identifier (e.g. "01", "02").
        category: Functional area (e.g. "functional", "ui", "api").
        description: What the feature does.
        steps: How to test this feature (explicit test steps).
        passes: Whether tests currently pass (starts False).
        priority: Higher = worked on first (100 = highest).
        last_tested: ISO timestamp of last test run, or None.
        evidence_id: Scout EvidenceRecord link when verified.
    """

    id: str
    category: str
    description: str
    steps: list[str] = field(default_factory=list)
    passes: bool = False
    priority: int = 100
    last_tested: str | None = None
    evidence_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "priority": self.priority,
            "last_tested": self.last_tested,
            "evidence_id": self.evidence_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Feature:
        return cls(
            id=data["id"],
            category=data["category"],
            description=data["description"],
            steps=data.get("steps", []),
            passes=data.get("passes", False),
            priority=data.get("priority", 100),
            last_tested=data.get("last_tested"),
            evidence_id=data.get("evidence_id"),
        )


@dataclass
class ProgressEntry:
    """A single session entry in progress.txt.

    Attributes:
        session_id: Unique session identifier.
        timestamp: ISO timestamp of the session.
        feature_id: ID of the feature worked on, or None for bug fixes.
        feature_description: What the feature does.
        actions_taken: List of actions performed.
        tests_run: List of test commands run.
        outcome: "passed", "failed", or "blocked".
        notes: Free-text notes.
    """

    session_id: str
    timestamp: str
    feature_id: str | None
    feature_description: str
    actions_taken: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    outcome: str = "pending"
    notes: str = ""

    def to_log_entry(self) -> str:
        """Format as a log entry for progress.txt."""
        lines = [
            f"--- Session {self.session_id} ---",
            f"Timestamp: {self.timestamp}",
            f"Feature: {self.feature_id or 'N/A'} - {self.feature_description}",
            f"Outcome: {self.outcome}",
        ]
        if self.actions_taken:
            lines.append("Actions:")
            for action in self.actions_taken:
                lines.append(f"  - {action}")
        if self.tests_run:
            lines.append("Tests:")
            for test in self.tests_run:
                lines.append(f"  - {test}")
        if self.notes:
            lines.append(f"Notes: {self.notes}")
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def now(cls, session_id: str, **kwargs) -> ProgressEntry:
        """Create a ProgressEntry with current timestamp."""
        return cls(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )
