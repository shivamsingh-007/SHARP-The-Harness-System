"""ArtifactManager: read/write durable artifacts (feature_list.json, progress.txt)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sharp.harness.artifacts.types import Feature, ProgressEntry
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class ArtifactManager:
    """Manages durable artifacts that bridge sessions.

    Artifacts:
    - feature_list.json: all features with passes status
    - progress.txt: structured session log
    - init.sh: startup script (read-only after creation)
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.feature_list_path = self.project_root / "feature_list.json"
        self.progress_path = self.project_root / "progress.txt"
        self.init_script_path = self.project_root / "init.sh"

    def health_check(self) -> bool:
        """Verify all required artifacts exist and are readable."""
        required = [self.feature_list_path, self.progress_path]
        for path in required:
            if not path.exists():
                logger.error(f"Missing artifact: {path.name}")
                return False
            if not path.is_file():
                logger.error(f"Not a file: {path.name}")
                return False
        return True

    # ── Feature List ──────────────────────────────────────────────────

    def read_features(self) -> list[Feature]:
        """Load feature_list.json into a list of Feature objects."""
        if not self.feature_list_path.exists():
            logger.warning("feature_list.json not found, returning empty list")
            return []

        raw = self.feature_list_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        # Support both list and dict with "checks" key
        if isinstance(data, dict) and "checks" in data:
            items = data["checks"]
        elif isinstance(data, list):
            items = data
        else:
            logger.error("feature_list.json has unexpected structure")
            return []

        return [Feature.from_dict(item) for item in items]

    def write_features(self, features: list[Feature]) -> None:
        """Write feature_list.json from a list of Feature objects."""
        data = {
            "version": "1.0",
            "project": "SHARP Enhanced",
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "checks": [f.to_dict() for f in features],
        }
        self.feature_list_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Wrote {len(features)} features to feature_list.json")

    def get_next_feature(self) -> Feature | None:
        """Return highest-priority feature where passes=False."""
        features = self.read_features()
        incomplete = [f for f in features if not f.passes]
        if not incomplete:
            return None
        incomplete.sort(key=lambda f: f.priority, reverse=True)
        return incomplete[0]

    def get_incomplete_features(self) -> list[Feature]:
        """Return all features where passes=False, sorted by priority."""
        features = self.read_features()
        incomplete = [f for f in features if not f.passes]
        incomplete.sort(key=lambda f: f.priority, reverse=True)
        return incomplete

    def get_completed_count(self) -> tuple[int, int]:
        """Return (completed_count, total_count)."""
        features = self.read_features()
        completed = sum(1 for f in features if f.passes)
        return completed, len(features)

    def mark_feature_passing(
        self,
        feature_id: str,
        evidence_id: str | None = None,
    ) -> bool:
        """Mark a feature as passing. Returns True if found and updated."""
        features = self.read_features()
        for f in features:
            if f.id == feature_id:
                f.passes = True
                f.last_tested = datetime.now(timezone.utc).isoformat()
                if evidence_id:
                    f.evidence_id = evidence_id
                self.write_features(features)
                logger.info(f"Feature {feature_id} marked as passing")
                return True
        logger.warning(f"Feature {feature_id} not found")
        return False

    # ── Progress Log ──────────────────────────────────────────────────

    def read_progress(self) -> str:
        """Read progress.txt content."""
        if not self.progress_path.exists():
            return ""
        return self.progress_path.read_text(encoding="utf-8")

    def append_progress(self, entry: ProgressEntry) -> None:
        """Append a session entry to progress.txt."""
        content = self.read_progress()
        new_entry = entry.to_log_entry()

        if content:
            content = content.rstrip("\n") + "\n\n" + new_entry
        else:
            content = new_entry

        self.progress_path.write_text(content, encoding="utf-8")
        logger.info(f"Appended progress for session {entry.session_id}")

    def init_progress(self) -> None:
        """Create an empty progress.txt with header if it doesn't exist."""
        if self.progress_path.exists():
            return
        header = (
            "SHARP Enhanced — Progress Notes\n"
            "================================\n\n"
        )
        self.progress_path.write_text(header, encoding="utf-8")
        logger.info("Created progress.txt with header")
