"""Tests for the CodingAgent (Phases 2-4: session start, DPEVR, end)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from sharp.harness.agents.coding import (
    CodingAgent, CodingConfig, SessionState, DPEVRStep, DPEVRResult, FeatureResult, run_shell
)
from sharp.harness.artifacts.manager import ArtifactManager
from sharp.harness.artifacts.types import Feature
from sharp.harness.execution.hooks import HookRegistry, HookEvent


def _setup_project(tmp_path, features=None):
    """Create a minimal project structure for testing."""
    sharp_dir = tmp_path / "sharp"
    sharp_dir.mkdir()
    (sharp_dir / "__init__.py").write_text('from sharp import HarnessEngine\n', encoding="utf-8")

    if features is None:
        features = [
            Feature(id="01", category="core", description="Feature 1", passes=False, priority=100),
            Feature(id="02", category="core", description="Feature 2", passes=False, priority=80),
            Feature(id="03", category="ui", description="Feature 3", passes=True, priority=60),
        ]
    data = {"checks": [f.to_dict() for f in features]}
    (tmp_path / "feature_list.json").write_text(json.dumps(data), encoding="utf-8")

    (tmp_path / "progress.txt").write_text(
        "SHARP Enhanced \u2014 Progress Notes\n================================\n",
        encoding="utf-8",
    )

    return ArtifactManager(tmp_path)


def _make_agent(tmp_path, features=None, max_attempts=3):
    """Helper to create a configured CodingAgent."""
    mgr = _setup_project(tmp_path, features=features)
    config = CodingConfig(project_root=str(tmp_path), max_feature_attempts=max_attempts)
    return CodingAgent(config, artifact_manager=mgr)


class TestRunShell:
    def test_run_shell_success(self):
        success, output = run_shell("python -c \"print('hello')\"")
        assert success is True
        assert "hello" in output

    def test_run_shell_failure(self):
        success, output = run_shell("python -c \"import sys; sys.exit(1)\"")
        assert success is False

    def test_run_shell_timeout(self):
        success, output = run_shell("python -c \"import time; time.sleep(10)\"", timeout=1)
        assert success is False
        assert "timed out" in output

    def test_run_shell_cwd(self, tmp_path):
        (tmp_path / "test.txt").write_text("found", encoding="utf-8")
        success, output = run_shell(
            "python -c \"print(open('test.txt').read().strip())\"",
            cwd=tmp_path,
        )
        assert success is True
        assert "found" in output


class TestCodingConfig:
    def test_default_config(self):
        config = CodingConfig()
        assert config.project_root == "."
        assert config.max_feature_attempts == 3

    def test_custom_config(self):
        config = CodingConfig(project_root="/tmp/project", max_feature_attempts=5)
        assert config.project_root == "/tmp/project"
        assert config.max_feature_attempts == 5


class TestSessionState:
    def test_default_state(self):
        state = SessionState()
        assert state.app_healthy is False
        assert state.next_feature is None
        assert state.incomplete_count == 0

    def test_state_with_data(self):
        f = Feature(id="01", category="core", description="Test", passes=False)
        state = SessionState(
            app_healthy=True,
            next_feature=f,
            incomplete_count=5,
            completed_count=2,
        )
        assert state.app_healthy is True
        assert state.next_feature.id == "01"
        assert state.incomplete_count == 5


class TestCodingAgentStartSession:
    @pytest.mark.asyncio
    async def test_start_session_wrong_directory(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        (tmp_path / "sharp" / "__init__.py").unlink()
        state = await agent.start_session()
        assert state.app_healthy is False
        assert state.next_feature is None

    @pytest.mark.asyncio
    async def test_start_session_reads_progress(self, tmp_path):
        mgr = _setup_project(tmp_path)
        (tmp_path / "progress.txt").write_text("Previous session: built feature X", encoding="utf-8")
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value="abc123 initial"):
            state = await agent.start_session()
        assert "Previous session" in state.progress_summary

    @pytest.mark.asyncio
    async def test_start_session_reads_git_log(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value="abc123 initial commit"):
            state = await agent.start_session()
        assert "abc123" in state.recent_commits

    @pytest.mark.asyncio
    async def test_start_session_picks_next_feature(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()
        assert state.next_feature is not None
        assert state.next_feature.id == "01"
        assert state.incomplete_count == 2
        assert state.completed_count == 1

    @pytest.mark.asyncio
    async def test_start_session_no_incomplete_features(self, tmp_path):
        features = [Feature(id="01", category="core", description="Done", passes=True)]
        mgr = _setup_project(tmp_path, features=features)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()
        assert state.next_feature is None
        assert state.incomplete_count == 0
        assert state.completed_count == 1

    @pytest.mark.asyncio
    async def test_start_session_init_script_fails(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=False), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()
        assert state.next_feature is not None

    @pytest.mark.asyncio
    async def test_start_session_app_broken(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=False), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()
        assert state.app_healthy is False

    @pytest.mark.asyncio
    async def test_start_session_app_healthy(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()
        assert state.app_healthy is True

    @pytest.mark.asyncio
    async def test_start_session_fires_hook(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        hook_registry = HookRegistry()
        events = []
        async def track(ctx):
            events.append(ctx.event.value)
        hook_registry.register(HookEvent.SESSION_START, track)
        agent = CodingAgent(config, artifact_manager=mgr, hook_registry=hook_registry)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            await agent.start_session()
        assert "session_start" in events

    @pytest.mark.asyncio
    async def test_start_session_generates_session_id(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        assert agent.session_id.startswith("session_")

    @pytest.mark.asyncio
    async def test_start_session_all_steps_logged(self, tmp_path):
        mgr = _setup_project(tmp_path)
        config = CodingConfig(project_root=str(tmp_path))
        agent = CodingAgent(config, artifact_manager=mgr)
        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value="abc commit"):
            state = await agent.start_session()
        assert state.app_healthy is True
        assert state.next_feature is not None
        assert state.recent_commits == "abc commit"
        assert "Progress Notes" in state.progress_summary


class TestCodingAgentDPEVR:
    @pytest.mark.asyncio
    async def test_dpevr_success_on_first_attempt(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        assert result.success is True
        assert result.tests_passed is True
        assert result.attempts == 1
        assert len(result.steps) == 5  # detect, prompt, execute, validate, respond

    @pytest.mark.asyncio
    async def test_dpevr_retries_on_failure(self, tmp_path):
        agent = _make_agent(tmp_path, max_attempts=2)
        feature = Feature(id="01", category="core", description="Test", passes=False)

        call_count = 0
        def mock_validate(feat):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (False, "FAIL attempt 1")
            return (True, "PASS attempt 2")

        with patch.object(agent, "_validate_feature", side_effect=mock_validate), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        assert result.success is True
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_dpevr_all_attempts_fail(self, tmp_path):
        agent = _make_agent(tmp_path, max_attempts=2)
        feature = Feature(id="01", category="core", description="Test", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(False, "FAIL")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        assert result.success is False
        assert result.attempts == 2
        assert "All 2 attempts failed" in result.notes

    @pytest.mark.asyncio
    async def test_dpevr_steps_recorded(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        phases = [s.phase for s in result.steps]
        assert phases == ["detect", "prompt", "execute", "validate", "respond"]

    @pytest.mark.asyncio
    async def test_dpevr_detect_step_has_feature_info(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="My Feature", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        detect = result.steps[0]
        assert detect.phase == "detect"
        assert "01" in detect.action
        assert "My Feature" in detect.action

    @pytest.mark.asyncio
    async def test_dpevr_prompt_step_has_context(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False,
                         steps=["test_imports", "test_create"])

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        prompt = result.steps[1]
        assert prompt.phase == "prompt"
        assert "test_imports" in prompt.output

    @pytest.mark.asyncio
    async def test_dpevr_fires_hooks(self, tmp_path):
        hook_registry = HookRegistry()
        events = []
        async def track(ctx):
            events.append(ctx.event.value)
        hook_registry.register(HookEvent.BEFORE_EXECUTE, track)
        hook_registry.register(HookEvent.AFTER_EXECUTE, track)

        agent = _make_agent(tmp_path)
        agent.hooks = hook_registry
        feature = Feature(id="01", category="core", description="Test", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            await agent.run_dpevr(feature)

        assert "before_execute" in events
        assert "after_execute" in events

    @pytest.mark.asyncio
    async def test_dpevr_fires_on_validation_failure(self, tmp_path):
        hook_registry = HookRegistry()
        events = []
        async def track(ctx):
            events.append(ctx.event.value)
        hook_registry.register(HookEvent.ON_VALIDATION_FAILURE, track)

        agent = _make_agent(tmp_path, max_attempts=1)
        agent.hooks = hook_registry
        feature = Feature(id="01", category="core", description="Test", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(False, "FAIL")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            await agent.run_dpevr(feature)

        assert "on_validation_failure" in events

    @pytest.mark.asyncio
    async def test_dpevr_duration_recorded(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False)

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="executed"):
            result = await agent.run_dpevr(feature)

        assert result.total_duration_ms > 0

    @pytest.mark.asyncio
    async def test_dpevr_cancellation_by_hook(self, tmp_path):
        hook_registry = HookRegistry()
        async def cancel(ctx):
            ctx.cancel = True
        hook_registry.register(HookEvent.BEFORE_EXECUTE, cancel)

        agent = _make_agent(tmp_path)
        agent.hooks = hook_registry
        feature = Feature(id="01", category="core", description="Test", passes=False)

        result = await agent.run_dpevr(feature)

        # Should be cancelled — not successful, only detect + prompt steps
        assert result.success is False
        phases = [s.phase for s in result.steps]
        assert "execute" not in phases

    @pytest.mark.asyncio
    async def test_build_prompt_context(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False,
                         steps=["step1", "step2"])
        ctx = agent._build_prompt_context(feature)
        assert "Test" in ctx
        assert "step1" in ctx
        assert "REMAINING FEATURES" in ctx


class TestCodingAgentEndSession:
    @pytest.mark.asyncio
    async def test_end_session_updates_progress(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test feature", passes=False)
        result = DPEVRResult(
            success=True, feature_id="01",
            steps=[DPEVRStep(phase="detect", action="pick", output="ok")],
            tests_passed=True, attempts=1, total_duration_ms=500,
        )

        with patch.object(agent, "_git_commit", return_value=True):
            await agent.end_session(feature=feature, result=result)

        progress = (tmp_path / "progress.txt").read_text(encoding="utf-8")
        assert "session_" in progress
        assert "PASS" in progress

    @pytest.mark.asyncio
    async def test_end_session_commits_git(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test feature", passes=False)
        result = DPEVRResult(
            success=True, feature_id="01",
            steps=[], tests_passed=True, attempts=1, total_duration_ms=500,
        )

        with patch.object(agent, "_git_commit", return_value=True) as mock_commit:
            await agent.end_session(feature=feature, result=result)
            mock_commit.assert_called_once_with(feature)

    @pytest.mark.asyncio
    async def test_end_session_marks_feature_passing(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False)
        result = DPEVRResult(
            success=True, feature_id="01",
            steps=[], tests_passed=True, attempts=1, total_duration_ms=500,
        )

        with patch.object(agent, "_git_commit", return_value=True):
            await agent.end_session(feature=feature, result=result)

        # Verify feature marked passing
        features = agent.artifacts.read_features()
        f = next(f for f in features if f.id == "01")
        assert f.passes is True

    @pytest.mark.asyncio
    async def test_end_session_does_not_mark_on_failure(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="Test", passes=False)
        result = DPEVRResult(
            success=False, feature_id="01",
            steps=[], tests_passed=False, attempts=3, total_duration_ms=1000,
            notes="All attempts failed",
        )

        with patch.object(agent, "_git_commit", return_value=True):
            await agent.end_session(feature=feature, result=result)

        features = agent.artifacts.read_features()
        f = next(f for f in features if f.id == "01")
        assert f.passes is False

    @pytest.mark.asyncio
    async def test_end_session_no_feature(self, tmp_path):
        agent = _make_agent(tmp_path)
        await agent.end_session(feature=None, result=None)
        # Should not crash

    @pytest.mark.asyncio
    async def test_end_session_fires_hook(self, tmp_path):
        hook_registry = HookRegistry()
        events = []
        async def track(ctx):
            events.append(ctx.event.value)
        hook_registry.register(HookEvent.SESSION_END, track)

        agent = _make_agent(tmp_path)
        agent.hooks = hook_registry

        with patch.object(agent, "_git_commit", return_value=True):
            await agent.end_session()

        assert "session_end" in events

    @pytest.mark.asyncio
    async def test_end_session_progress_content(self, tmp_path):
        agent = _make_agent(tmp_path)
        feature = Feature(id="01", category="core", description="My Feature", passes=False)
        step = DPEVRStep(phase="execute", action="wrote code", output="done", success=True, duration_ms=123)
        result = DPEVRResult(
            success=True, feature_id="01",
            steps=[step], tests_passed=True, attempts=1, total_duration_ms=500,
            notes="All good",
        )

        with patch.object(agent, "_git_commit", return_value=True):
            await agent.end_session(feature=feature, result=result)

        progress = (tmp_path / "progress.txt").read_text(encoding="utf-8")
        assert "My Feature" in progress
        assert "1 attempt" in progress or "Attempts: 1" in progress
        assert "0.5s" in progress
        assert "wrote code" in progress
        assert "All good" in progress
