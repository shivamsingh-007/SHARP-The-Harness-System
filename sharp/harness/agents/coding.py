"""CodingAgent: repeats every session, reads artifacts, runs DPEVR, updates artifacts.

Session lifecycle:
1. start_session() — read artifacts, test app, pick feature
2. run_dpevr() — detect -> prompt -> execute -> validate -> respond
3. end_session() — git commit, update progress, mark feature
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sharp.harness.artifacts.manager import ArtifactManager
from sharp.harness.artifacts.types import Feature, ProgressEntry
from sharp.harness.execution.hooks import HookRegistry, HookEvent, HookContext
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CodingConfig:
    """Configuration for the CodingAgent."""

    project_root: str = "."
    max_feature_attempts: int = 3
    session_timeout_seconds: int = 3600
    engine_config: dict[str, Any] | None = None  # HarnessConfig kwargs for real LLM


@dataclass
class SessionState:
    """State recovered at session start."""

    app_healthy: bool = False
    next_feature: Feature | None = None
    progress_summary: str = ""
    recent_commits: str = ""
    incomplete_count: int = 0
    completed_count: int = 0


@dataclass
class FeatureResult:
    """Result of attempting a feature."""

    success: bool
    feature_id: str
    actions_taken: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    notes: str = ""
    evidence_id: str | None = None


@dataclass
class DPEVRStep:
    """Record of a single DPEVR step."""

    phase: str  # "detect", "prompt", "execute", "validate", "respond"
    action: str
    output: str
    success: bool = True
    duration_ms: float = 0.0


@dataclass
class DPEVRResult:
    """Result of a full DPEVR loop iteration."""

    success: bool
    feature_id: str
    steps: list[DPEVRStep] = field(default_factory=list)
    tests_passed: bool = False
    attempts: int = 0
    total_duration_ms: float = 0.0
    notes: str = ""


ALLOWED_COMMANDS = frozenset({
    "git", "python", "python3", "pip", "pip3",
    "pytest", "ls", "cat", "grep", "find", "bash",
})


def run_shell(
    command: str,
    cwd: str | Path = ".",
    timeout: int = 30,
    project_root: str | Path | None = None,
) -> tuple[bool, str]:
    """Run a command safely with allowlist enforcement.

    Uses shell=False with argument list. No shell metacharacters are interpreted.

    Args:
        command: Command string (will be split via shlex).
        cwd: Working directory.
        timeout: Timeout in seconds.
        project_root: If set, cwd must resolve within this directory.

    Returns:
        Tuple of (success: bool, output: str).
    """
    if not command.strip():
        return False, "Empty command"

    try:
        parts = shlex.split(command)
    except ValueError as e:
        return False, f"Invalid command syntax: {e}"

    if not parts:
        return False, "Empty command"

    cmd_name = Path(parts[0]).name
    if cmd_name not in ALLOWED_COMMANDS:
        return False, f"Command not allowed: {cmd_name}. Allowed: {sorted(ALLOWED_COMMANDS)}"

    resolved_cwd = Path(cwd).resolve()
    if project_root:
        root = Path(project_root).resolve()
        if not resolved_cwd.is_relative_to(root):
            return False, f"CWD outside project root: {cwd}"

    try:
        result = subprocess.run(
            parts,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


class CodingAgent:
    """Repeats every session. Reads artifacts, runs DPEVR, updates artifacts.

    Session lifecycle:
    1. start_session() — read artifacts, test app, pick feature
    2. run_dpevr() — detect -> prompt -> execute -> validate -> respond
    3. end_session() — git commit, update progress, mark feature
    """

    def __init__(
        self,
        config: CodingConfig | None = None,
        artifact_manager: ArtifactManager | None = None,
        hook_registry: HookRegistry | None = None,
    ) -> None:
        self.config = config or CodingConfig()
        self.project_root = Path(self.config.project_root)
        self.artifacts = artifact_manager or ArtifactManager(self.config.project_root)
        self.hooks = hook_registry or HookRegistry()
        self.session_id = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")
        self._last_result: DPEVRResult | None = None

    # ── Session Start (Phase 2) ──────────────────────────────────────

    async def start_session(self) -> SessionState:
        """Read artifacts and test app health.

        6-step workflow:
        1. Confirm correct directory
        2. Read progress.txt (what happened before)
        3. Read git log (recent commits)
        4. Read feature_list.json (what needs doing)
        5. Run init.sh (start dev server)
        6. Test basic functionality (is app broken?)

        Returns SessionState with recovery info.
        """
        logger.info(f"Starting session {self.session_id}")
        state = SessionState()

        # Step 1: Confirm directory
        if not self._confirm_directory():
            logger.error("Wrong directory — aborting session")
            return state
        logger.info("[1/6] Directory confirmed")

        # Step 2: Read progress.txt
        state.progress_summary = self._read_progress_summary()
        logger.info(f"[2/6] Progress loaded ({len(state.progress_summary)} chars)")

        # Step 3: Read git log
        state.recent_commits = self._read_git_log()
        logger.info(f"[3/6] Git log loaded ({len(state.recent_commits)} chars)")

        # Step 4: Read feature_list.json
        state.next_feature = self.artifacts.get_next_feature()
        completed, total = self.artifacts.get_completed_count()
        state.completed_count = completed
        state.incomplete_count = total - completed
        logger.info(
            f"[4/6] Features loaded: {completed}/{total} passing, "
            f"next: {state.next_feature.id if state.next_feature else 'none'}"
        )

        # Step 5: Run init.sh
        init_ok = self._run_init_script()
        logger.info(f"[5/6] Init script: {'OK' if init_ok else 'FAILED'}")

        # Step 6: Test basic functionality
        state.app_healthy = self._test_basic_functionality()
        logger.info(f"[6/6] App health: {'HEALTHY' if state.app_healthy else 'BROKEN'}")

        # Fire session_start hook
        await self.hooks.fire(HookEvent.SESSION_START, HookContext(
            event=HookEvent.SESSION_START,
            data={
                "session_id": self.session_id,
                "state": state,
            },
        ))

        return state

    def _confirm_directory(self) -> bool:
        """Step 1: Verify we're in the right directory."""
        init_marker = self.project_root / "sharp" / "__init__.py"
        if not init_marker.exists():
            logger.error(f"Not in harness_system directory: {self.project_root}")
            return False
        return True

    def _read_progress_summary(self) -> str:
        """Step 2: Read progress.txt, return last 2000 chars."""
        content = self.artifacts.read_progress()
        if not content:
            return "No previous progress found."
        if len(content) > 2000:
            return "...\n" + content[-2000:]
        return content

    def _read_git_log(self) -> str:
        """Step 3: Read recent git commits."""
        success, output = run_shell(
            "git log --oneline -20",
            cwd=self.project_root,
            project_root=self.project_root,
        )
        if not success:
            return "No git history found."
        return output

    def _run_init_script(self) -> bool:
        """Step 5: Run init.sh to start dev server."""
        init_script = self.project_root / "init.sh"
        if not init_script.exists():
            logger.warning("init.sh not found, skipping")
            return False

        success, output = run_shell(
            f"bash {init_script}",
            cwd=self.project_root,
            timeout=60,
            project_root=self.project_root,
        )
        if not success:
            logger.warning(f"init.sh failed: {output[:200]}")
        return success

    def _test_basic_functionality(self) -> bool:
        """Step 6: Test if the app基本功能 works (imports + engine create)."""
        success, output = run_shell(
            'python -c "from sharp import HarnessEngine; e = HarnessEngine(); print(\'OK\')"',
            cwd=self.project_root,
            project_root=self.project_root,
        )
        return success

    # ── DPEVR Loop (Phase 3) ─────────────────────────────────────────

    async def run_dpevr(self, feature: Feature) -> DPEVRResult:
        """Run DPEVR loop on one feature.

        DETECT -> PROMPT -> EXECUTE -> VALIDATE -> RESPOND

        Args:
            feature: The feature to implement.

        Returns:
            DPEVRResult with step-by-step record.
        """
        start_time = time.time()
        steps: list[DPEVRStep] = []
        attempts = 0

        logger.info(f"DPEVR loop starting for feature {feature.id}: {feature.description}")

        for attempt in range(1, self.config.max_feature_attempts + 1):
            attempts = attempt
            logger.info(f"Attempt {attempt}/{self.config.max_feature_attempts}")

            # ── DETECT ──────────────────────────────────────────────
            detect_step = DPEVRStep(
                phase="detect",
                action=f"Selected feature {feature.id}: {feature.description}",
                output=f"Priority: {feature.priority}, Steps: {len(feature.steps)}",
            )
            steps.append(detect_step)

            # ── PROMPT ──────────────────────────────────────────────
            prompt_context = self._build_prompt_context(feature)
            prompt_step = DPEVRStep(
                phase="prompt",
                action="Built context from artifacts + git log",
                output=prompt_context[:500] + "..." if len(prompt_context) > 500 else prompt_context,
            )
            steps.append(prompt_step)

            # Fire before_execute hook
            before_ctx = await self.hooks.fire(HookEvent.BEFORE_EXECUTE, HookContext(
                event=HookEvent.BEFORE_EXECUTE,
                data={
                    "feature": feature,
                    "attempt": attempt,
                    "prompt_context": prompt_context,
                },
            ))
            if before_ctx.cancel:
                logger.info("DPEVR cancelled by before_execute hook")
                break

            # ── EXECUTE ─────────────────────────────────────────────
            exec_start = time.time()
            exec_output = await self._execute_feature(feature, prompt_context)
            exec_duration = (time.time() - exec_start) * 1000
            exec_step = DPEVRStep(
                phase="execute",
                action=f"Executed feature implementation",
                output=exec_output[:500],
                success=True,
                duration_ms=exec_duration,
            )
            steps.append(exec_step)

            # ── VALIDATE ────────────────────────────────────────────
            val_start = time.time()
            tests_passed, test_output = self._validate_feature(feature)
            val_duration = (time.time() - val_start) * 1000
            val_step = DPEVRStep(
                phase="validate",
                action=f"Ran test command for feature {feature.id}",
                output=test_output[:500],
                success=tests_passed,
                duration_ms=val_duration,
            )
            steps.append(val_step)

            # Fire after_execute hook
            await self.hooks.fire(HookEvent.AFTER_EXECUTE, HookContext(
                event=HookEvent.AFTER_EXECUTE,
                data={
                    "feature": feature,
                    "attempt": attempt,
                    "tests_passed": tests_passed,
                    "test_output": test_output,
                },
            ))

            # ── RESPOND ─────────────────────────────────────────────
            if tests_passed:
                respond_step = DPEVRStep(
                    phase="respond",
                    action=f"Feature {feature.id} tests PASSED",
                    output="Marking feature as passing",
                )
                steps.append(respond_step)
                logger.info(f"Feature {feature.id} PASSED on attempt {attempt}")

                total_duration = (time.time() - start_time) * 1000
                self._last_result = DPEVRResult(
                    success=True,
                    feature_id=feature.id,
                    steps=steps,
                    tests_passed=True,
                    attempts=attempts,
                    total_duration_ms=total_duration,
                )
                return self._last_result

            # Tests failed — log and retry
            respond_step = DPEVRStep(
                phase="respond",
                action=f"Feature {feature.id} tests FAILED on attempt {attempt}",
                output=test_output[:300],
                success=False,
            )
            steps.append(respond_step)
            logger.warning(f"Feature {feature.id} FAILED on attempt {attempt}: {test_output[:200]}")

            # Fire on_validation_failure hook
            await self.hooks.fire(HookEvent.ON_VALIDATION_FAILURE, HookContext(
                event=HookEvent.ON_VALIDATION_FAILURE,
                data={
                    "feature": feature,
                    "attempt": attempt,
                    "test_output": test_output,
                },
            ))

            # Fire on_retry hook if we will retry
            if attempt < self.config.max_feature_attempts:
                await self.hooks.fire(HookEvent.ON_RETRY, HookContext(
                    event=HookEvent.ON_RETRY,
                    data={
                        "feature": feature,
                        "attempt": attempt,
                    },
                ))

        # All attempts exhausted
        total_duration = (time.time() - start_time) * 1000
        self._last_result = DPEVRResult(
            success=False,
            feature_id=feature.id,
            steps=steps,
            tests_passed=False,
            attempts=attempts,
            total_duration_ms=total_duration,
            notes=f"All {attempts} attempts failed",
        )
        logger.error(f"Feature {feature.id} FAILED after {attempts} attempts")
        return self._last_result

    def _build_prompt_context(self, feature: Feature) -> str:
        """Build context string from artifacts for the feature."""
        parts = []

        # Feature definition
        parts.append(f"FEATURE: {feature.description}")
        parts.append(f"CATEGORY: {feature.category}")
        parts.append(f"STEPS TO TEST:")
        for step in feature.steps:
            parts.append(f"  - {step}")

        # Progress summary
        progress = self._read_progress_summary()
        if progress:
            parts.append(f"\nPREVIOUS PROGRESS:\n{progress[:1000]}")

        # Recent commits
        git_log = self._read_git_log()
        if git_log and git_log != "No git history found.":
            parts.append(f"\nRECENT COMMITS:\n{git_log[:500]}")

        # Incomplete features summary
        incomplete = self.artifacts.get_incomplete_features()
        if incomplete:
            parts.append(f"\nREMAINING FEATURES: {len(incomplete)} incomplete")
            for f in incomplete[:5]:
                parts.append(f"  - [{f.id}] {f.description}")

        return "\n".join(parts)

    async def _execute_feature(self, feature: Feature, context: str) -> str:
        """Execute the feature by calling the real LLM engine.

        Uses HarnessEngine to generate code/implementation for the feature.
        Falls back to shell test if no engine config is provided.
        """

        from sharp.harness.core.config import HarnessConfig
        from sharp.harness.core.engine import HarnessEngine

        # Build the prompt for the LLM
        prompt = (
            f"Implement the following feature:\n\n"
            f"Feature: {feature.id} - {feature.description}\n\n"
            f"Context:\n{context}\n\n"
            f"Steps to implement:\n"
        )
        for i, step in enumerate(feature.steps, 1):
            prompt += f"  {i}. {step}\n"
        prompt += (
            f"\nProvide the complete implementation. "
            f"Return only the code changes needed, no explanation."
        )

        # Try to use real engine if config is provided
        if self.config.engine_config:
            try:
                engine_config = HarnessConfig(**self.config.engine_config)
                engine = HarnessEngine(engine_config)
                result = await engine.run(prompt)
                if result.success and result.output:
                    logger.info(f"LLM generated implementation for {feature.id}")
                    return result.output
                logger.warning(f"LLM returned empty/failed for {feature.id}: {result.error}")
            except Exception as e:
                logger.warning(f"LLM execution failed for {feature.id}: {e}")

        # Fallback: run the feature's test command
        test_cmd = self._get_test_command(feature)
        if test_cmd:
            success, output = run_shell(test_cmd, cwd=self.project_root, timeout=30, project_root=self.project_root)
            return output

        return f"Feature {feature.id} implementation step completed"

    def _validate_feature(self, feature: Feature) -> tuple[bool, str]:
        """Validate the feature by running its test steps.

        Returns:
            Tuple of (tests_passed: bool, output: str).
        """
        # Run the test command for this feature
        test_cmd = self._get_test_command(feature)
        if test_cmd:
            success, output = run_shell(test_cmd, cwd=self.project_root, timeout=30, project_root=self.project_root)
            return success, output

        # No test command — check if basic imports work
        success, output = run_shell(
            'python -c "from sharp import HarnessEngine; print(\'OK\')"',
            cwd=self.project_root,
            project_root=self.project_root,
        )
        return success, output

    def _get_test_command(self, feature: Feature) -> str | None:
        """Get the test command for a feature based on its category."""
        category_commands = {
            "core": 'python -c "from sharp import HarnessEngine; e = HarnessEngine(); print(\'PASS\')"',
            "context": "python -m pytest tests/test_context.py -q --tb=short",
            "prompt": "python -m pytest tests/test_prompt.py -q --tb=short",
            "execution": "python -m pytest tests/test_loop.py -q --tb=short",
            "validation": "python -m pytest tests/test_validation.py -q --tb=short",
            "safety": "python -m pytest tests/test_safety.py -q --tb=short",
            "state": "python -m pytest tests/test_checkpoint.py -q --tb=short",
            "mcp": "python -m pytest tests/test_mcp/ -q --tb=short",
            "observability": "python -m pytest tests/test_metrics.py -q --tb=short",
            "integration": "python -m pytest tests/test_integration.py -q --tb=short",
        }
        return category_commands.get(feature.category)

    # ── Session End (Phase 4) ────────────────────────────────────────

    async def end_session(
        self,
        feature: Feature | None = None,
        result: DPEVRResult | None = None,
    ) -> None:
        """Update artifacts after coding.

        1. Git commit
        2. Update progress.txt
        3. Mark feature passes=true
        """
        logger.info(f"Ending session {self.session_id}")

        # Step 1: Git commit if feature was worked on
        if feature:
            commit_ok = self._git_commit(feature)
            logger.info(f"Git commit: {'OK' if commit_ok else 'FAILED/SKIPPED'}")

        # Step 2: Update progress.txt
        self._update_progress(feature, result)
        logger.info("Progress updated")

        # Step 3: Mark feature passing
        if result and result.success and feature:
            self.artifacts.mark_feature_passing(feature.id, result.feature_id)
            logger.info(f"Feature {feature.id} marked passing")

        # Fire session_end hook
        await self.hooks.fire(HookEvent.SESSION_END, HookContext(
            event=HookEvent.SESSION_END,
            data={
                "session_id": self.session_id,
                "feature_id": feature.id if feature else None,
                "success": result.success if result else False,
            },
        ))

    def _git_commit(self, feature: Feature) -> bool:
        """Git add and commit with a message about the feature."""
        # Stage all changes
        ok1, _ = run_shell("git add .", cwd=self.project_root, project_root=self.project_root)
        if not ok1:
            return False

        # Commit using subprocess list (no shell injection)
        msg = f"feat({feature.category}): {feature.description}"
        try:
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _update_progress(
        self,
        feature: Feature | None,
        result: DPEVRResult | None,
    ) -> None:
        """Append to progress.txt with session summary."""
        lines = []
        lines.append(f"\n## Session {self.session_id}")
        lines.append(f"Date: {datetime.now(timezone.utc).isoformat()}")

        if feature:
            lines.append(f"Feature: {feature.id} — {feature.description}")

        if result:
            lines.append(f"Result: {'PASS' if result.success else 'FAIL'}")
            lines.append(f"Attempts: {result.attempts}")
            lines.append(f"Duration: {result.total_duration_ms/1000:.1f}s")

            if result.steps:
                lines.append("Steps:")
                for step in result.steps:
                    status = "OK" if step.success else "FAIL"
                    lines.append(f"  [{status}] {step.phase}: {step.action}")

            if result.notes:
                lines.append(f"Notes: {result.notes}")
        else:
            lines.append("Result: No feature attempted")

        lines.append("")

        content = "\n".join(lines)
        progress_path = self.artifacts.progress_path
        with open(progress_path, "a", encoding="utf-8") as f:
            f.write(content)
