"""Tests for the InitializerAgent."""

import pytest
from pathlib import Path
from sharp.harness.agents.initializer import InitializerAgent, InitializerConfig


class TestInitializerAgent:
    @pytest.mark.asyncio
    async def test_run_creates_artifacts(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=5)
        agent = InitializerAgent(config)
        result = await agent.run()

        assert result.success is True
        assert result.features_created == 5
        assert "feature_list.json" in result.artifacts
        assert "progress.txt" in result.artifacts

    @pytest.mark.asyncio
    async def test_feature_list_is_valid_json(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=10)
        agent = InitializerAgent(config)
        await agent.run()

        import json
        data = json.loads((tmp_path / "feature_list.json").read_text())
        assert "checks" in data
        assert len(data["checks"]) == 10

    @pytest.mark.asyncio
    async def test_all_features_start_failing(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=10)
        agent = InitializerAgent(config)
        await agent.run()

        features = agent.artifact_manager.read_features()
        assert all(not f.passes for f in features)

    @pytest.mark.asyncio
    async def test_features_have_steps(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=10)
        agent = InitializerAgent(config)
        await agent.run()

        features = agent.artifact_manager.read_features()
        for f in features:
            assert len(f.steps) > 0, f"Feature {f.id} has no steps"

    @pytest.mark.asyncio
    async def test_progress_txt_has_header(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=5)
        agent = InitializerAgent(config)
        await agent.run()

        content = (tmp_path / "progress.txt").read_text(encoding="utf-8")
        assert "Progress Notes" in content

    @pytest.mark.asyncio
    async def test_idempotent_run(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=5)
        agent = InitializerAgent(config)

        result1 = await agent.run()
        assert result1.success is True

        result2 = await agent.run()
        assert result2.success is True

        # Should not duplicate artifacts
        features = agent.artifact_manager.read_features()
        assert len(features) == 5

    @pytest.mark.asyncio
    async def test_max_features_respected(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=3)
        agent = InitializerAgent(config)
        result = await agent.run()

        assert result.features_created == 3
        features = agent.artifact_manager.read_features()
        assert len(features) == 3

    @pytest.mark.asyncio
    async def test_features_cover_all_zones(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=20)
        agent = InitializerAgent(config)
        await agent.run()

        features = agent.artifact_manager.read_features()
        categories = {f.category for f in features}
        expected = {"core", "context", "prompt", "execution", "validation", "safety"}
        assert expected.issubset(categories)

    @pytest.mark.asyncio
    async def test_result_has_artifacts_list(self, tmp_path):
        config = InitializerConfig(project_root=str(tmp_path), max_features=5)
        agent = InitializerAgent(config)
        result = await agent.run()

        assert isinstance(result.artifacts, list)
        assert len(result.artifacts) >= 2
