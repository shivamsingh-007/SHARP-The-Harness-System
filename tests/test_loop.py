"""Tests for execution/loop.py - ReAct/CoT/ToT execution loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sharp.harness.execution.loop import ExecutionLoop, LoopState
from sharp.harness.core.config import ExecutionConfig
from sharp.harness.core.types import LoopStrategy, ToolDefinition, RiskLevel
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.core.config import ToolConfig


class TestLoopState:
    def test_default_state(self):
        state = LoopState()
        assert state.iteration == 0
        assert state.history == []
        assert state.tool_calls == []
        assert state.observations == []
        assert state.done is False
        assert state.final_answer == ""


class TestExecutionLoop:
    @pytest.fixture
    def loop(self):
        config = ExecutionConfig(max_iterations=5, loop_strategy=LoopStrategy.REACT)
        tool_config = ToolConfig()
        registry = ToolRegistry(tool_config)
        return ExecutionLoop(config, registry)

    def test_reset(self, loop):
        loop.record_thought("test thought")
        loop.increment()
        loop.reset()
        assert loop.state.iteration == 0
        assert loop.state.history == []

    def test_should_continue(self, loop):
        assert loop.should_continue() is True
        loop.set_done("answer")
        assert loop.should_continue() is False

    def test_should_continue_max_iterations(self, loop):
        for _ in range(5):
            loop.increment()
        assert loop.should_continue() is False

    def test_record_thought(self, loop):
        loop.record_thought("I need to search")
        assert len(loop.state.history) == 1
        assert loop.state.history[0]["type"] == "thought"
        assert loop.state.history[0]["content"] == "I need to search"

    def test_record_action(self, loop):
        loop.record_action("search", {"query": "test"})
        assert len(loop.state.tool_calls) == 1
        assert loop.state.tool_calls[0]["tool"] == "search"

    def test_record_observation(self, loop):
        loop.record_observation("Found result")
        assert len(loop.state.observations) == 1
        assert loop.state.observations[0] == "Found result"
        assert len(loop.state.history) == 1

    def test_set_done(self, loop):
        loop.set_done("final answer")
        assert loop.state.done is True
        assert loop.state.final_answer == "final answer"

    def test_increment(self, loop):
        assert loop.state.iteration == 0
        loop.increment()
        assert loop.state.iteration == 1
        loop.increment()
        assert loop.state.iteration == 2

    def test_build_loop_prompt_first_iteration(self, loop):
        prompt = loop.build_loop_prompt("What is Python?")
        assert "What is Python?" in prompt
        assert "Previous Steps" not in prompt

    def test_build_loop_prompt_with_history(self, loop):
        loop.increment()
        loop.record_thought("Need to search")
        loop.record_action("search", {"query": "Python"})
        loop.record_observation("Python is a language")

        prompt = loop.build_loop_prompt("What is Python?")
        assert "Previous Steps" in prompt
        assert "Thought: Need to search" in prompt
        assert "Observation: Python is a language" in prompt


class TestExecutionLoopParsing:
    @pytest.fixture
    def loop(self):
        config = ExecutionConfig(max_iterations=5)
        tool_config = ToolConfig()
        registry = ToolRegistry(tool_config)
        return ExecutionLoop(config, registry)

    def test_parse_final_answer(self, loop):
        content = "Thought: I know the answer\nFinal Answer: Python is a programming language."
        parsed = loop._parse_llm_response(content)
        assert parsed["type"] == "final_answer"
        assert "Python" in parsed["content"]

    def test_parse_action(self, loop):
        content = 'Thought: I need to search\nAction: search(query="Python docs")'
        parsed = loop._parse_llm_response(content)
        assert parsed["type"] == "action"
        assert parsed["tool"] == "search"
        assert parsed["arguments"]["query"] == "Python docs"

    def test_parse_thought(self, loop):
        content = "Thought: I need to think about this more carefully."
        parsed = loop._parse_llm_response(content)
        assert parsed["type"] == "thought"
        assert "think about this" in parsed["content"]

    def test_parse_action_complex_args(self, loop):
        content = 'Action: tool(name="test", count=5, flag=true)'
        parsed = loop._parse_llm_response(content)
        assert parsed["type"] == "action"
        assert parsed["arguments"]["name"] == "test"
        assert parsed["arguments"]["count"] == 5
        assert parsed["arguments"]["flag"] is True

    def test_parse_empty_content(self, loop):
        parsed = loop._parse_llm_response("")
        assert parsed["type"] == "thought"

    def test_parse_action_no_args(self, loop):
        content = "Action: simple_tool()"
        parsed = loop._parse_llm_response(content)
        assert parsed["type"] == "action"
        assert parsed["tool"] == "simple_tool"
        assert parsed["arguments"] == {}


class TestExecutionLoopRun:
    @pytest.mark.asyncio
    async def test_run_simple_final_answer(self):
        """Test loop that gives a final answer immediately."""
        config = ExecutionConfig(max_iterations=5, loop_strategy=LoopStrategy.REACT)
        tool_config = ToolConfig()
        registry = ToolRegistry(tool_config)
        loop = ExecutionLoop(config, registry)

        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=MagicMock(
            content="Final Answer: The answer is 42.",
        ))

        result = await loop.run(provider, "What is the answer?")
        assert result == "The answer is 42."
        assert loop.state.done is True

    @pytest.mark.asyncio
    async def test_run_with_tool_calls(self):
        """Test loop that uses tools before answering."""
        config = ExecutionConfig(max_iterations=5, loop_strategy=LoopStrategy.REACT)
        tool_config = ToolConfig()
        registry = ToolRegistry(tool_config)
        loop = ExecutionLoop(config, registry)

        # Register a mock tool
        async def mock_search(query: str) -> str:
            return f"Results for: {query}"

        tool_def = ToolDefinition(
            name="search",
            description="Search",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        registry.register(mock_search, tool_def)

        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=[
            MagicMock(content='Thought: I need to search\nAction: search(query="test")'),
            MagicMock(content="Thought: Got results\nFinal Answer: Here are the results."),
        ])

        result = await loop.run(provider, "Search for test")
        assert "results" in result.lower()
        assert len(loop.state.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_run_max_iterations(self):
        """Test loop stops at max iterations."""
        config = ExecutionConfig(max_iterations=2, loop_strategy=LoopStrategy.REACT)
        tool_config = ToolConfig()
        registry = ToolRegistry(tool_config)
        loop = ExecutionLoop(config, registry)

        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=MagicMock(
            content="Thought: Still thinking...",
        ))

        result = await loop.run(provider, "Think hard")
        assert loop.state.iteration == 2
        assert loop.state.done is False
