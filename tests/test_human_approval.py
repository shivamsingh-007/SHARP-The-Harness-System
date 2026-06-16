"""Tests for safety/human_approval.py - HITL gates."""

import asyncio
import pytest
from sharp.harness.safety.human_approval import HumanApprovalGate


class TestHumanApprovalGate:
    @pytest.fixture
    def gate(self):
        return HumanApprovalGate()

    @pytest.mark.asyncio
    async def test_auto_reject_no_callback(self, gate):
        """No callback configured → reject by default (safe default)."""
        result = await gate.request_approval("tool1")
        assert result is False

    @pytest.mark.asyncio
    async def test_approve_with_callback(self, gate):
        async def approve(tool_name, context):
            return True

        gate.set_approval_callback(approve)
        result = await gate.request_approval("tool1")
        assert result is True

    @pytest.mark.asyncio
    async def test_reject_with_callback(self, gate):
        async def reject(tool_name, context):
            return False

        gate.set_approval_callback(reject)
        result = await gate.request_approval("tool1")
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout(self, gate):
        async def slow_approve(tool_name, context):
            await asyncio.sleep(10)
            return True

        gate.set_approval_callback(slow_approve)
        result = await gate.request_approval("tool1", timeout=0.1)
        assert result is False

    def test_approve_pending(self, gate):
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        gate._pending["req-1"] = future
        gate.approve("req-1")
        assert future.result() is True

    def test_reject_pending(self, gate):
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        gate._pending["req-1"] = future
        gate.reject("req-1")
        assert future.result() is False

    def test_get_pending(self, gate):
        import asyncio
        loop = asyncio.new_event_loop()
        gate._pending["a"] = loop.create_future()
        gate._pending["b"] = loop.create_future()
        pending = gate.get_pending()
        assert len(pending) == 2
        loop.close()
