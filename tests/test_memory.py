"""Tests for context/memory.py - Persistent memory manager."""

import json
import pytest
from pathlib import Path
from sharp.harness.context.memory import MemoryManager


class TestMemoryManager:
    @pytest.fixture
    def manager(self, tmp_path):
        return MemoryManager(memory_dir=str(tmp_path / "memory"))

    def test_init_creates_directory(self, tmp_path):
        mem_dir = tmp_path / "new_memory"
        MemoryManager(memory_dir=str(mem_dir))
        assert mem_dir.exists()

    def test_set_session(self, manager):
        manager.set_session("key", "value")
        assert manager.get("key") == "value"

    def test_set_persistent(self, manager):
        manager.set_persistent("key", "value")
        assert manager.get("key") == "value"
        # Verify it's saved to disk
        memory_file = Path(manager._memory_dir) / "memory.json"
        assert memory_file.exists()
        data = json.loads(memory_file.read_text())
        assert data["key"] == "value"

    def test_session_overrides_persistent(self, manager):
        manager.set_persistent("key", "persistent")
        manager.set_session("key", "session")
        assert manager.get("key") == "session"

    def test_get_all(self, manager):
        manager.set_persistent("k1", "v1")
        manager.set_session("k2", "v2")
        all_mem = manager.get_all()
        assert all_mem["k1"] == "v1"
        assert all_mem["k2"] == "v2"

    def test_get_memory_summary(self, manager):
        manager.set_session("topic", "Python basics")
        summary = manager.get_memory_summary()
        assert "Memory" in summary
        assert "Python basics" in summary

    def test_get_memory_summary_empty(self, manager):
        summary = manager.get_memory_summary()
        assert summary == ""

    def test_clear_session(self, manager):
        manager.set_session("k", "v")
        manager.clear_session()
        assert manager.get("k") is None

    def test_delete_persistent(self, manager):
        manager.set_persistent("key", "value")
        result = manager.delete_persistent("key")
        assert result is True
        assert manager.get("key") is None

    def test_delete_persistent_not_found(self, manager):
        result = manager.delete_persistent("nonexistent")
        assert result is False

    def test_load_from_file(self, manager, tmp_path):
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("# Project Rules\nUse type hints.")
        manager.load_from_file(str(md_file))
        assert "CLAUDE.md" in manager.get_all()

    def test_persistence_across_instances(self, tmp_path):
        mem_dir = str(tmp_path / "memory")
        m1 = MemoryManager(memory_dir=mem_dir)
        m1.set_persistent("key", "value")

        m2 = MemoryManager(memory_dir=mem_dir)
        assert m2.get("key") == "value"
