"""Tests for context engineering zone."""

import pytest
from sharp.harness.context.curator import ContextCurator
from sharp.harness.context.compressor import ContextCompressor
from sharp.harness.context.memory import MemoryManager
from sharp.harness.context.sources import ContextSource, ContextSourceManager
from sharp.harness.core.config import ContextConfig


class TestContextSourceManager:
    def test_add_user_request(self):
        manager = ContextSourceManager()
        source = manager.add_user_request("Hello world")
        assert source.source_type == "user"
        assert source.priority == -1

    def test_add_memory(self):
        manager = ContextSourceManager()
        source = manager.add_memory("key", "value")
        assert source.source_type == "memory"
        assert "memory:key" in source.name

    def test_get_sorted(self):
        manager = ContextSourceManager()
        manager.add_user_request("High priority", priority=-1)
        manager.add_memory("key", "Low priority", priority=5)
        sorted_sources = manager.get_sorted()
        assert sorted_sources[0].priority == -1


class TestContextCompressor:
    def test_no_compression_needed(self):
        compressor = ContextCompressor(total_budget=1000)
        content = "Short content"
        result = compressor.compress(content)
        assert result == content

    def test_truncation(self):
        compressor = ContextCompressor(total_budget=10)
        content = "x" * 100
        result = compressor.compress(content)
        assert len(result) < len(content)

    def test_deduplication(self):
        compressor = ContextCompressor(dedup_threshold=0.8)
        contents = ["Hello world", "Hello world!", "Goodbye"]
        result = compressor.deduplicate(contents)
        assert len(result) <= len(contents)


class TestMemoryManager:
    def test_set_get_session(self):
        manager = MemoryManager()
        manager.set_session("key", "value")
        assert manager.get("key") == "value"

    def test_session_overrides_persistent(self):
        manager = MemoryManager()
        manager.set_persistent("key", "persistent")
        manager.set_session("key", "session")
        assert manager.get("key") == "session"

    def test_clear_session(self):
        manager = MemoryManager()
        manager.set_session("unique_key_123", "value")
        manager.clear_session()
        assert manager.get("unique_key_123") is None


class TestContextCurator:
    def test_curate_basic(self):
        config = ContextConfig(total_token_budget=10000)
        curator = ContextCurator(config)
        result = curator.curate(
            user_request="Test request",
            memory={"key": "value"},
        )
        assert len(result.sources) > 0
        assert result.total_tokens > 0
