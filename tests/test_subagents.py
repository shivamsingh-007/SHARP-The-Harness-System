"""Tests for execution/subagents.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sharp.harness.execution.subagents import SubAgentManager, SubAgentDefinition, SubAgentResult
from tests.conftest import MockLLMProvider


class TestSubAgentDefinition:
    def test_create_definition(self):
        defn = SubAgentDefinition(
            name="test_agent",
            role="Tester",
            instructions="Test things thoroughly.",
        )
        assert defn.name == "test_agent"
        assert defn.role == "Tester"
        assert defn.tools == []
        assert defn.max_iterations == 5


class TestSubAgentManager:
    def test_register(self):
        manager = SubAgentManager()
        defn = SubAgentDefinition(name="agent1", role="Role", instructions="Do stuff.")
        manager.register(defn)
        assert len(manager.list_agents()) == 1

    def test_get(self):
        manager = SubAgentManager()
        defn = SubAgentDefinition(name="agent1", role="Role", instructions="Do stuff.")
        manager.register(defn)
        result = manager.get("agent1")
        assert result is not None
        assert result.name == "agent1"

    def test_get_not_found(self):
        manager = SubAgentManager()
        assert manager.get("nonexistent") is None

    def test_list_agents(self):
        manager = SubAgentManager()
        manager.register(SubAgentDefinition(name="a1", role="R1", instructions="I1"))
        manager.register(SubAgentDefinition(name="a2", role="R2", instructions="I2"))
        agents = manager.list_agents()
        assert len(agents) == 2

    def test_deactivate(self):
        manager = SubAgentManager()
        manager._active["test"] = "something"
        manager.deactivate("test")
        assert "test" not in manager._active


class TestSubAgentSpawn:
    @pytest.mark.asyncio
    async def test_spawn_not_found(self):
        manager = SubAgentManager()
        provider = MockLLMProvider()
        result = await manager.spawn("nonexistent", "do something", provider)
        assert result.success is False
        assert "not found" in result.output.lower() or "not registered" in result.error.lower()

    @pytest.mark.asyncio
    async def test_spawn_success(self):
        manager = SubAgentManager()
        manager.register(SubAgentDefinition(
            name="researcher",
            role="Researcher",
            instructions="Find information.",
        ))
        provider = MockLLMProvider(responses=["Research complete. Found answer."])
        result = await manager.spawn("researcher", "Find info about X", provider)
        assert result.success is True
        assert "Research complete" in result.output
        assert result.agent_name == "researcher"

    @pytest.mark.asyncio
    async def test_spawn_with_context(self):
        manager = SubAgentManager()
        manager.register(SubAgentDefinition(
            name="coder",
            role="Coder",
            instructions="Write code.",
        ))
        provider = MockLLMProvider(responses=["def hello(): return 'hello'"])
        result = await manager.spawn(
            "coder", "Write hello function", provider,
            context={"language": "python"},
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_spawn_failure(self):
        manager = SubAgentManager()
        manager.register(SubAgentDefinition(
            name="agent",
            role="Agent",
            instructions="Do work.",
        ))
        provider = MockLLMProvider()
        provider.complete = AsyncMock(side_effect=Exception("LLM down"))
        result = await manager.spawn("agent", "Do work", provider)
        assert result.success is False
        assert "LLM down" in result.error

    @pytest.mark.asyncio
    async def test_get_result(self):
        manager = SubAgentManager()
        manager.register(SubAgentDefinition(
            name="agent", role="Agent", instructions="Work."
        ))
        provider = MockLLMProvider(responses=["Done!"])
        await manager.spawn("agent", "task", provider)
        result = manager.get_result("agent")
        assert result is not None
        assert result.output == "Done!"
