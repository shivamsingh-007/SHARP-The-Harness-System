"""Tests for state/persistence.py - Persistence backends."""

import json
import pytest
from sharp.harness.state.persistence import FileBackend


class TestFileBackend:
    @pytest.fixture
    def backend(self, tmp_path):
        return FileBackend(base_dir=str(tmp_path / "storage"))

    def test_set_and_get(self, backend):
        backend.set("key1", "value1")
        result = backend.get("key1")
        assert result == "value1"

    def test_get_nonexistent(self, backend):
        result = backend.get("nonexistent")
        assert result is None

    def test_delete(self, backend):
        backend.set("key1", "value1")
        result = backend.delete("key1")
        assert result is True
        assert backend.get("key1") is None

    def test_delete_nonexistent(self, backend):
        result = backend.delete("nonexistent")
        assert result is False

    def test_list_keys(self, backend):
        backend.set("prefix:a", "1")
        backend.set("prefix:b", "2")
        backend.set("other:c", "3")
        keys = backend.list_keys("prefix:")
        assert len(keys) == 2

    def test_list_keys_all(self, backend):
        backend.set("a", "1")
        backend.set("b", "2")
        keys = backend.list_keys()
        assert len(keys) == 2

    def test_overwrite(self, backend):
        backend.set("key", "old")
        backend.set("key", "new")
        assert backend.get("key") == "new"
