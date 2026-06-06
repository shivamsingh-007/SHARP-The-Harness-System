"""Tests for state/checkpoint.py - Checkpoint manager."""

import json
import pytest
from sharp.harness.state.checkpoint import CheckpointManager, Checkpoint
from sharp.harness.core.config import StateConfig


class TestCheckpointManager:
    @pytest.fixture
    def manager(self, tmp_path):
        config = StateConfig(
            enabled=True,
            backend="file",
            checkpoint_dir=str(tmp_path / "checkpoints"),
        )
        return CheckpointManager(config)

    def test_save_and_load(self, manager):
        manager.save("trace-1", context=[], output="test output")
        loaded = manager.load("trace-1")
        assert loaded is not None
        assert loaded.trace_id == "trace-1"
        assert loaded.output == "test output"

    def test_load_nonexistent(self, manager):
        loaded = manager.load("nonexistent")
        assert loaded is None

    def test_save_disabled(self, tmp_path):
        config = StateConfig(enabled=False, checkpoint_dir=str(tmp_path / "cp"))
        manager = CheckpointManager(config)
        manager.save("trace-1", output="data")
        loaded = manager.load("trace-1")
        assert loaded is None

    def test_list_checkpoints(self, manager):
        manager.save("t1", output="a")
        manager.save("t2", output="b")
        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) == 2

    def test_delete_checkpoint(self, manager):
        manager.save("trace-1", output="data")
        result = manager.delete("trace-1")
        assert result is True
        loaded = manager.load("trace-1")
        assert loaded is None

    def test_delete_nonexistent(self, manager):
        result = manager.delete("nonexistent")
        assert result is False

    def test_save_with_metadata(self, manager):
        manager.save("trace-1", output="data", metadata={"key": "value"})
        loaded = manager.load("trace-1")
        assert loaded is not None
        assert loaded.metadata.get("key") == "value"
