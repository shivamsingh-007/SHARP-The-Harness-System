"""ContextAggregator: merges context from all sources into a unified view.

Combines:
- User's current prompt
- Git repo state (recent commits, current branch, diff)
- File system (relevant files for task)
- Previous SHARP sessions (progress.txt, feature_list.json)
- Interface histories (if user started in one interface, continued in another)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sharp.harness.artifacts.manager import ArtifactManager
from sharp.harness.context.curator import ContextCurator
from sharp.harness.context.sources import ContextSource
from sharp.harness.orchestration.types import (
    ContextAggregation,
    InterfaceRequest,
    InterfaceType,
)
from sharp.harness.agents.coding import run_shell
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AggregatorConfig:
    """Configuration for the ContextAggregator."""

    project_root: str = "."
    max_file_content_chars: int = 10000
    max_git_log_entries: int = 20
    max_git_diff_lines: int = 200
    include_previous_sessions: bool = True


class ContextAggregator:
    """Merges context from all sources into a unified ContextAggregation.

    Sources:
    1. Interface request (what the user asked, which interface they're on)
    2. Git repo state (commits, diff, branch)
    3. File system (relevant files)
    4. SHARP artifacts (features, progress)
    5. Interface histories (cross-interface memory)
    """

    def __init__(self, config: AggregatorConfig | None = None) -> None:
        self.config = config or AggregatorConfig()
        self.project_root = Path(self.config.project_root)
        self.artifacts = ArtifactManager(self.config.project_root)
        self._interface_histories: dict[InterfaceType, list[str]] = {}

    def aggregate(
        self,
        request: InterfaceRequest,
        context_curator: ContextCurator | None = None,
    ) -> ContextAggregation:
        """Build a complete context aggregation for a request.

        Args:
            request: The normalized interface request.
            context_curator: Optional SHARP context curator for additional context.

        Returns:
            ContextAggregation with all merged context.
        """
        logger.info(f"Aggregating context for {request.interface.value} request")

        # 1. Start with the task description
        task_description = request.user_prompt

        # 2. Collect relevant files
        relevant_files = list(request.files_involved)
        file_contents = self._read_relevant_files(relevant_files)

        # 3. Get git state
        git_diff = self._get_git_diff()
        git_log = self._get_git_log()

        # 4. Get SHARP artifact state
        progress_summary = self._get_progress_summary()
        feature_state = self._get_feature_state()

        # 5. Get interface histories (cross-interface memory)
        interface_histories = dict(self._interface_histories)

        # 6. Record this request in the originating interface's history
        self._record_history(request.interface, request.user_prompt)

        # 7. Merge any additional context from the request
        extra_files = request.context.get("files", [])
        for f in extra_files:
            if f not in relevant_files:
                relevant_files.append(f)
                contents = self._read_file(f)
                if contents:
                    file_contents[f] = contents

        extra_context = request.context.get("additional_context", "")

        aggregation = ContextAggregation(
            task_description=task_description,
            relevant_files=relevant_files,
            file_contents=file_contents,
            git_diff=git_diff,
            git_log=git_log,
            progress_summary=progress_summary,
            feature_state=feature_state,
            interface_histories=interface_histories,
            metadata={
                "interface": request.interface.value,
                "session_id": request.session_id,
                "branch": request.branch,
                "extra_context": extra_context,
            },
        )

        logger.info(
            f"Context aggregated: {len(relevant_files)} files, "
            f"{len(file_contents)} contents, "
            f"{len(git_log)} git log chars"
        )

        return aggregation

    def inject_into_curator(
        self,
        aggregation: ContextAggregation,
        context_curator: ContextCurator,
    ) -> list[ContextSource]:
        """Convert aggregation into ContextSources for SHARP's context curator.

        This bridges the orchestration layer with SHARP's existing
        context engineering system.
        """
        sources = []

        # Git diff as context
        if aggregation.git_diff:
            sources.append(ContextSource(
                name="git_diff",
                content=aggregation.git_diff[:self.config.max_git_diff_lines * 100],
                source_type="tool_output",
                priority=3,
            ))

        # Git log as context
        if aggregation.git_log:
            sources.append(ContextSource(
                name="git_log",
                content=aggregation.git_log,
                source_type="tool_output",
                priority=4,
            ))

        # File contents
        for filename, content in aggregation.file_contents.items():
            truncated = content[:self.config.max_file_content_chars]
            sources.append(ContextSource(
                name=f"file:{filename}",
                content=truncated,
                source_type="tool_output",
                priority=2,
            ))

        # Progress summary
        if aggregation.progress_summary:
            sources.append(ContextSource(
                name="progress",
                content=aggregation.progress_summary,
                source_type="memory",
                priority=5,
            ))

        # Interface histories
        for interface, history in aggregation.interface_histories.items():
            if history:
                history_text = "\n".join(history[-5:])  # Last 5 entries
                sources.append(ContextSource(
                    name=f"history:{interface}",
                    content=history_text,
                    source_type="memory",
                    priority=6,
                ))

        return sources

    def record_interface_history(
        self,
        interface: InterfaceType,
        prompt: str,
        response_summary: str = "",
    ) -> None:
        """Record an interaction in an interface's history for cross-interface memory."""
        entry = prompt
        if response_summary:
            entry += f" -> {response_summary[:100]}"
        self._record_history(interface, entry)

    def _record_history(self, interface: InterfaceType, text: str) -> None:
        """Internal: append to interface history."""
        if interface not in self._interface_histories:
            self._interface_histories[interface] = []
        self._interface_histories[interface].append(text)
        # Keep last 20 entries per interface
        if len(self._interface_histories[interface]) > 20:
            self._interface_histories[interface] = self._interface_histories[interface][-20:]

    # ── Git Helpers ────────────────────────────────────────────────────

    def _get_git_diff(self) -> str:
        """Get staged + unstaged diff."""
        success, output = run_shell(
            "git diff HEAD --stat",
            cwd=self.project_root,
            timeout=10,
        )
        if not success:
            return ""
        return output

    def _get_git_log(self) -> str:
        """Get recent git log."""
        success, output = run_shell(
            f"git log --oneline -{self.config.max_git_log_entries}",
            cwd=self.project_root,
            timeout=10,
        )
        if not success:
            return ""
        return output

    # ── File Helpers ───────────────────────────────────────────────────

    def _read_relevant_files(self, files: list[str]) -> dict[str, str]:
        """Read contents of relevant files."""
        contents = {}
        for filepath in files:
            content = self._read_file(filepath)
            if content:
                contents[filepath] = content
        return contents

    def _read_file(self, filepath: str) -> str | None:
        """Read a file's content, handling errors gracefully."""
        try:
            path = self.project_root / filepath
            if path.exists() and path.is_file():
                content = path.read_text(encoding="utf-8")
                return content[:self.config.max_file_content_chars]
        except Exception as e:
            logger.warning(f"Failed to read {filepath}: {e}")
        return None

    # ── Artifact Helpers ───────────────────────────────────────────────

    def _get_progress_summary(self) -> str:
        """Read progress.txt, return last 2000 chars."""
        if not self.config.include_previous_sessions:
            return ""
        content = self.artifacts.read_progress()
        if not content:
            return ""
        if len(content) > 2000:
            return "...\n" + content[-2000:]
        return content

    def _get_feature_state(self) -> dict[str, Any]:
        """Get current feature state summary."""
        features = self.artifacts.read_features()
        if not features:
            return {}
        completed, total = self.artifacts.get_completed_count()
        return {
            "total": total,
            "completed": completed,
            "passing_rate": f"{completed}/{total}",
            "next_feature": features[0].id if features else None,
        }
