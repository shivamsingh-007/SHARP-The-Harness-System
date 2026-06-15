"""Integration test: multi-session coding workflow.

Tests the full lifecycle:
  ArtifactManager setup -> CodingAgent.start_session -> run_dpevr -> end_session
across multiple simulated sessions with artifact persistence.

Uses mock for directory check since tests run in tmp_path, not the real project.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from sharp.harness.agents.coding import CodingAgent, CodingConfig, DPEVRResult, DPEVRStep
from sharp.harness.artifacts.manager import ArtifactManager
from sharp.harness.artifacts.types import Feature
from sharp.harness.execution.hooks import HookRegistry, HookEvent


def _setup_project(tmp_path, features=None):
    """Bootstrap project artifacts directly (no InitializerAgent dependency)."""
    mgr = ArtifactManager(tmp_path)

    # Only write features if not already present (preserve across sessions)
    if not mgr.feature_list_path.exists():
        if features is None:
            features = [
                Feature(id="01", category="core", description="Core engine works",
                        passes=False, priority=100,
                        steps=["Import HarnessEngine", "Create engine", "Verify not None"]),
                Feature(id="02", category="context", description="Context curation works",
                        passes=False, priority=80,
                        steps=["Import ContextCurator", "Create curator", "Verify sources"]),
                Feature(id="03", category="validation", description="Validation works",
                        passes=False, priority=60,
                        steps=["Import OutputValidator", "Create validator", "Verify checks"]),
            ]
        mgr.write_features(features)

    if not mgr.progress_path.exists():
        mgr.init_progress()

    # Create sharp/__init__.py so directory check passes
    sharp_dir = tmp_path / "sharp"
    sharp_dir.mkdir(exist_ok=True)
    (sharp_dir / "__init__.py").write_text(
        "from sharp import HarnessEngine\n", encoding="utf-8"
    )

    return mgr


def _make_agent(tmp_path, features=None, max_attempts=2, hook_registry=None):
    """Create a CodingAgent with all shell calls mocked."""
    mgr = _setup_project(tmp_path, features)
    config = CodingConfig(
        project_root=str(tmp_path),
        max_feature_attempts=max_attempts,
    )
    agent = CodingAgent(
        config=config,
        artifact_manager=mgr,
        hook_registry=hook_registry or HookRegistry(),
    )
    return agent


def _mock_session(agent):
    """Return a context manager that mocks all shell calls for start_session."""
    return (
        patch.object(agent, "_run_init_script", return_value=True),
        patch.object(agent, "_test_basic_functionality", return_value=True),
        patch.object(agent, "_read_git_log", return_value=""),
    )


class TestSingleSession:
    """Test a full single session: start -> DPEVR -> end."""

    @pytest.mark.asyncio
    async def test_full_single_session_pass(self, tmp_path):
        """Session starts, DPEVR passes on first attempt, ends cleanly."""
        agent = _make_agent(tmp_path)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature
        assert feature is not None
        assert feature.id == "01"

        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            dpevr_result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=dpevr_result)

        assert dpevr_result.success is True
        assert dpevr_result.attempts == 1

        # Feature should be marked passing
        features = agent.artifacts.read_features()
        f = next(f for f in features if f.id == "01")
        assert f.passes is True

        # Progress should have session entry
        progress = agent.artifacts.read_progress()
        assert "PASS" in progress

    @pytest.mark.asyncio
    async def test_full_single_session_fail_then_pass(self, tmp_path):
        """Session starts, DPEVR fails first attempt, passes second."""
        agent = _make_agent(tmp_path)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature
        attempt = 0

        def mock_validate(feat):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                return (False, "FAIL: import error")
            return (True, "PASS")

        with patch.object(agent, "_validate_feature", side_effect=mock_validate), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            dpevr_result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=dpevr_result)

        assert dpevr_result.success is True
        assert dpevr_result.attempts == 2

    @pytest.mark.asyncio
    async def test_full_single_session_all_fail(self, tmp_path):
        """Session starts, DPEVR fails all attempts, feature stays incomplete."""
        agent = _make_agent(tmp_path)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature

        with patch.object(agent, "_validate_feature", return_value=(False, "FAIL")), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            dpevr_result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=dpevr_result)

        assert dpevr_result.success is False
        assert dpevr_result.attempts == 2

        # Feature should still be incomplete
        features = agent.artifacts.read_features()
        f = next(f for f in features if f.id == "01")
        assert f.passes is False


class TestMultiSession:
    """Test multiple sessions progressing through features."""

    @pytest.mark.asyncio
    async def test_two_sessions_progress(self, tmp_path):
        """Session 1 passes feature 1, session 2 picks feature 2."""
        # ── Session 1 ──
        agent1 = _make_agent(tmp_path)
        with patch.object(agent1, "_run_init_script", return_value=True), \
             patch.object(agent1, "_test_basic_functionality", return_value=True), \
             patch.object(agent1, "_read_git_log", return_value=""):
            state1 = await agent1.start_session()

        feature1 = state1.next_feature
        assert feature1 is not None
        assert feature1.id == "01"

        with patch.object(agent1, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent1, "_execute_feature", return_value="done"), \
             patch.object(agent1, "_git_commit", return_value=True):
            result1 = await agent1.run_dpevr(feature1)
            await agent1.end_session(feature=feature1, result=result1)

        assert result1.success is True

        # ── Session 2 ──
        agent2 = _make_agent(tmp_path)
        with patch.object(agent2, "_run_init_script", return_value=True), \
             patch.object(agent2, "_test_basic_functionality", return_value=True), \
             patch.object(agent2, "_read_git_log", return_value="commit abc"):
            state2 = await agent2.start_session()

        # Session 2 should pick a different feature
        assert state2.next_feature is not None
        assert state2.next_feature.id != feature1.id
        assert state2.completed_count >= 1
        assert state2.incomplete_count >= 1

        # Session 2 passes its feature
        feature2 = state2.next_feature
        with patch.object(agent2, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent2, "_execute_feature", return_value="done"), \
             patch.object(agent2, "_git_commit", return_value=True):
            result2 = await agent2.run_dpevr(feature2)
            await agent2.end_session(feature=feature2, result=result2)

        assert result2.success is True

        # Both features should be passing
        features = agent2.artifacts.read_features()
        passing = [f for f in features if f.passes]
        assert len(passing) >= 2

    @pytest.mark.asyncio
    async def test_three_sessions_all_complete(self, tmp_path):
        """Three sessions complete all 3 features."""
        for session_num in range(3):
            agent = _make_agent(tmp_path)
            with patch.object(agent, "_run_init_script", return_value=True), \
                 patch.object(agent, "_test_basic_functionality", return_value=True), \
                 patch.object(agent, "_read_git_log", return_value=f"session {session_num}"):
                state = await agent.start_session()

            feature = state.next_feature
            if feature is None:
                break  # All done

            with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
                 patch.object(agent, "_execute_feature", return_value="done"), \
                 patch.object(agent, "_git_commit", return_value=True):
                result = await agent.run_dpevr(feature)
                await agent.end_session(feature=feature, result=result)

            assert result.success is True

        # All features should be passing
        agent = _make_agent(tmp_path)
        features = agent.artifacts.read_features()
        assert all(f.passes for f in features)
        assert len(features) == 3

    @pytest.mark.asyncio
    async def test_session_recovers_progress_from_previous(self, tmp_path):
        """Session 2 reads progress.txt written by session 1."""
        # Session 1
        agent1 = _make_agent(tmp_path)
        with patch.object(agent1, "_run_init_script", return_value=True), \
             patch.object(agent1, "_test_basic_functionality", return_value=True), \
             patch.object(agent1, "_read_git_log", return_value=""):
            await agent1.start_session()

        feature1 = agent1.artifacts.get_next_feature()
        with patch.object(agent1, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent1, "_execute_feature", return_value="done"), \
             patch.object(agent1, "_git_commit", return_value=True):
            r1 = await agent1.run_dpevr(feature1)
            await agent1.end_session(feature=feature1, result=r1)

        # Session 2
        agent2 = _make_agent(tmp_path)
        with patch.object(agent2, "_run_init_script", return_value=True), \
             patch.object(agent2, "_test_basic_functionality", return_value=True), \
             patch.object(agent2, "_read_git_log", return_value=""):
            state2 = await agent2.start_session()

        # Progress should contain session 1 info
        assert "PASS" in state2.progress_summary or "session_" in state2.progress_summary


class TestHookIntegration:
    """Test hooks fire correctly across the full lifecycle."""

    @pytest.mark.asyncio
    async def test_hooks_fire_in_order(self, tmp_path):
        """All hooks fire in expected order across session."""
        hook_registry = HookRegistry()
        events = []

        async def track(ctx):
            events.append(ctx.event.value)

        hook_registry.register(HookEvent.SESSION_START, track)
        hook_registry.register(HookEvent.BEFORE_EXECUTE, track)
        hook_registry.register(HookEvent.AFTER_EXECUTE, track)
        hook_registry.register(HookEvent.SESSION_END, track)

        agent = _make_agent(tmp_path, hook_registry=hook_registry)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature
        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=result)

        assert events == [
            "session_start",
            "before_execute",
            "after_execute",
            "session_end",
        ]

    @pytest.mark.asyncio
    async def test_retry_hooks_fire_on_failure(self, tmp_path):
        """on_retry and on_validation_failure hooks fire on failed attempts."""
        hook_registry = HookRegistry()
        events = []

        async def track(ctx):
            events.append(ctx.event.value)

        hook_registry.register(HookEvent.ON_VALIDATION_FAILURE, track)
        hook_registry.register(HookEvent.ON_RETRY, track)

        agent = _make_agent(tmp_path, hook_registry=hook_registry)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature
        attempt = 0

        def mock_validate(feat):
            nonlocal attempt
            attempt += 1
            return (False, "FAIL") if attempt == 1 else (True, "PASS")

        with patch.object(agent, "_validate_feature", side_effect=mock_validate), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=result)

        assert "on_validation_failure" in events
        assert "on_retry" in events


class TestArtifactPersistence:
    """Test artifacts persist correctly across operations."""

    @pytest.mark.asyncio
    async def test_feature_list_json_valid(self, tmp_path):
        """feature_list.json remains valid JSON after all operations."""
        agent = _make_agent(tmp_path)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature
        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=result)

        # JSON should be valid
        raw = (tmp_path / "feature_list.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "checks" in data
        assert len(data["checks"]) == 3

    @pytest.mark.asyncio
    async def test_progress_txt_grows(self, tmp_path):
        """progress.txt accumulates entries from multiple sessions."""
        for _ in range(2):
            agent = _make_agent(tmp_path)
            with patch.object(agent, "_run_init_script", return_value=True), \
                 patch.object(agent, "_test_basic_functionality", return_value=True), \
                 patch.object(agent, "_read_git_log", return_value=""):
                state = await agent.start_session()

            feature = state.next_feature
            if feature is None:
                break
            with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
                 patch.object(agent, "_execute_feature", return_value="done"), \
                 patch.object(agent, "_git_commit", return_value=True):
                result = await agent.run_dpevr(feature)
                await agent.end_session(feature=feature, result=result)

        progress = (tmp_path / "progress.txt").read_text(encoding="utf-8")
        assert progress.count("## Session") >= 2

    @pytest.mark.asyncio
    async def test_health_check_passes(self, tmp_path):
        """ArtifactManager health check passes after full lifecycle."""
        agent = _make_agent(tmp_path)

        with patch.object(agent, "_run_init_script", return_value=True), \
             patch.object(agent, "_test_basic_functionality", return_value=True), \
             patch.object(agent, "_read_git_log", return_value=""):
            state = await agent.start_session()

        feature = state.next_feature
        with patch.object(agent, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent, "_execute_feature", return_value="done"), \
             patch.object(agent, "_git_commit", return_value=True):
            result = await agent.run_dpevr(feature)
            await agent.end_session(feature=feature, result=result)

        assert agent.artifacts.health_check() is True

    @pytest.mark.asyncio
    async def test_marked_features_persist(self, tmp_path):
        """Features marked passing persist across agent instances."""
        # Agent 1: pass feature 01
        agent1 = _make_agent(tmp_path)
        with patch.object(agent1, "_run_init_script", return_value=True), \
             patch.object(agent1, "_test_basic_functionality", return_value=True), \
             patch.object(agent1, "_read_git_log", return_value=""):
            state = await agent1.start_session()

        feature = state.next_feature
        with patch.object(agent1, "_validate_feature", return_value=(True, "PASS")), \
             patch.object(agent1, "_execute_feature", return_value="done"), \
             patch.object(agent1, "_git_commit", return_value=True):
            r = await agent1.run_dpevr(feature)
            await agent1.end_session(feature=feature, result=r)

        # Agent 2: fresh instance, feature 01 should still be passing
        agent2 = _make_agent(tmp_path)
        features = agent2.artifacts.read_features()
        f01 = next(f for f in features if f.id == "01")
        assert f01.passes is True
        assert f01.last_tested is not None
