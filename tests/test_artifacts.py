"""Tests for the artifact system (types + manager)."""

import json
import pytest
from pathlib import Path
from sharp.harness.artifacts.types import Feature, ProgressEntry
from sharp.harness.artifacts.manager import ArtifactManager


class TestFeature:
    def test_create_feature(self):
        f = Feature(
            id="01",
            category="core",
            description="Engine initializes",
            steps=["Import", "Create", "Verify"],
        )
        assert f.id == "01"
        assert f.passes is False
        assert f.priority == 100

    def test_feature_to_dict(self):
        f = Feature(id="01", category="core", description="Test", steps=["s1"])
        d = f.to_dict()
        assert d["id"] == "01"
        assert d["passes"] is False
        assert d["steps"] == ["s1"]

    def test_feature_from_dict(self):
        d = {
            "id": "01",
            "category": "core",
            "description": "Test",
            "steps": ["s1"],
            "passes": True,
            "priority": 80,
        }
        f = Feature.from_dict(d)
        assert f.id == "01"
        assert f.passes is True
        assert f.priority == 80

    def test_feature_roundtrip(self):
        f = Feature(id="01", category="core", description="Test", steps=["s1"])
        d = f.to_dict()
        f2 = Feature.from_dict(d)
        assert f.id == f2.id
        assert f.description == f2.description
        assert f.steps == f2.steps


class TestProgressEntry:
    def test_create_entry(self):
        e = ProgressEntry(
            session_id="s1",
            timestamp="2026-01-01T00:00:00Z",
            feature_id="01",
            feature_description="Test feature",
        )
        assert e.session_id == "s1"
        assert e.outcome == "pending"

    def test_to_log_entry(self):
        e = ProgressEntry(
            session_id="s1",
            timestamp="2026-01-01T00:00:00Z",
            feature_id="01",
            feature_description="Test feature",
            actions_taken=["wrote code"],
            tests_run=["pytest tests/"],
            outcome="passed",
        )
        log = e.to_log_entry()
        assert "Session s1" in log
        assert "passed" in log
        assert "wrote code" in log

    def test_now_factory(self):
        e = ProgressEntry.now(
            session_id="s1",
            feature_id="01",
            feature_description="Test",
        )
        assert e.session_id == "s1"
        assert "T" in e.timestamp  # ISO format


class TestArtifactManager:
    @pytest.fixture
    def tmp_artifacts(self, tmp_path):
        """Create a temporary project with feature_list.json and progress.txt."""
        features = [
            Feature(id="01", category="core", description="Feature 1", passes=False, priority=100),
            Feature(id="02", category="core", description="Feature 2", passes=True, priority=80),
            Feature(id="03", category="ui", description="Feature 3", passes=False, priority=60),
        ]
        data = {
            "version": "1.0",
            "checks": [f.to_dict() for f in features],
        }
        (tmp_path / "feature_list.json").write_text(json.dumps(data, indent=2))
        (tmp_path / "progress.txt").write_text(
            "SHARP Enhanced — Progress Notes\n", encoding="utf-8"
        )
        return ArtifactManager(tmp_path)

    def test_health_check_passes(self, tmp_artifacts):
        assert tmp_artifacts.health_check() is True

    def test_health_check_fails_missing(self, tmp_path):
        mgr = ArtifactManager(tmp_path)
        assert mgr.health_check() is False

    def test_read_features(self, tmp_artifacts):
        features = tmp_artifacts.read_features()
        assert len(features) == 3
        assert features[0].id == "01"

    def test_write_features(self, tmp_artifacts, tmp_path):
        features = tmp_artifacts.read_features()
        features.append(Feature(id="04", category="api", description="New"))
        tmp_artifacts.write_features(features)
        reloaded = tmp_artifacts.read_features()
        assert len(reloaded) == 4

    def test_get_next_feature(self, tmp_artifacts):
        f = tmp_artifacts.get_next_feature()
        assert f is not None
        assert f.id == "01"  # highest priority among incomplete
        assert f.passes is False

    def test_get_next_feature_none_when_all_pass(self, tmp_path):
        features = [Feature(id="01", category="core", description="Test", passes=True)]
        data = {"checks": [f.to_dict() for f in features]}
        (tmp_path / "feature_list.json").write_text(json.dumps(data))
        (tmp_path / "progress.txt").write_text("")
        mgr = ArtifactManager(tmp_path)
        assert mgr.get_next_feature() is None

    def test_get_incomplete_features(self, tmp_artifacts):
        incomplete = tmp_artifacts.get_incomplete_features()
        assert len(incomplete) == 2
        assert all(not f.passes for f in incomplete)

    def test_get_completed_count(self, tmp_artifacts):
        completed, total = tmp_artifacts.get_completed_count()
        assert completed == 1
        assert total == 3

    def test_mark_feature_passing(self, tmp_artifacts):
        result = tmp_artifacts.mark_feature_passing("01", evidence_id="ev_001")
        assert result is True
        f = tmp_artifacts.read_features()
        f01 = [x for x in f if x.id == "01"][0]
        assert f01.passes is True
        assert f01.evidence_id == "ev_001"
        assert f01.last_tested is not None

    def test_mark_feature_not_found(self, tmp_artifacts):
        result = tmp_artifacts.mark_feature_passing("99")
        assert result is False

    def test_read_progress(self, tmp_artifacts):
        content = tmp_artifacts.read_progress()
        assert "Progress Notes" in content

    def test_append_progress(self, tmp_artifacts):
        entry = ProgressEntry.now(
            session_id="s1",
            feature_id="01",
            feature_description="Test",
            outcome="passed",
        )
        tmp_artifacts.append_progress(entry)
        content = tmp_artifacts.read_progress()
        assert "Session s1" in content
        assert "passed" in content

    def test_init_progress_creates_header(self, tmp_path):
        mgr = ArtifactManager(tmp_path)
        mgr.init_progress()
        assert (tmp_path / "progress.txt").exists()
        content = (tmp_path / "progress.txt").read_text(encoding="utf-8")
        assert "Progress Notes" in content

    def test_init_progress_idempotent(self, tmp_path):
        mgr = ArtifactManager(tmp_path)
        (tmp_path / "progress.txt").write_text("existing content", encoding="utf-8")
        mgr.init_progress()
        content = (tmp_path / "progress.txt").read_text(encoding="utf-8")
        assert content == "existing content"
