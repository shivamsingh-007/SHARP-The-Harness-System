"""Tests for state/session.py - Session manager."""

import pytest
from sharp.harness.state.session import SessionManager, Session


class TestSessionManager:
    @pytest.fixture
    def manager(self):
        return SessionManager(ttl=3600)

    def test_create_session(self, manager):
        session = manager.create()
        assert isinstance(session, Session)
        assert session.session_id is not None
        assert len(session.session_id) > 0

    def test_get_session(self, manager):
        session = manager.create()
        retrieved = manager.get(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent(self, manager):
        assert manager.get("nonexistent") is None

    def test_add_trace(self, manager):
        session = manager.create()
        manager.add_trace(session.session_id, "trace-1")
        manager.add_trace(session.session_id, "trace-2")
        assert len(session.trace_ids) == 2

    def test_add_trace_nonexistent_session(self, manager):
        manager.add_trace("nonexistent", "trace-1")  # Should not raise

    def test_list_active(self, manager):
        s1 = manager.create()
        s2 = manager.create()
        active = manager.list_active()
        assert len(active) == 2

    def test_close_session(self, manager):
        session = manager.create()
        manager.close(session.session_id)
        assert manager.get(session.session_id) is None

    def test_create_with_metadata(self, manager):
        session = manager.create(metadata={"user": "test"})
        assert session.metadata["user"] == "test"
