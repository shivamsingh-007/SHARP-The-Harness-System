"""Execution loop - ReAct/CoT/ToT execution strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sharp.harness.core.config import ExecutionConfig
from sharp.harness.core.types import LoopStrategy, ToolDefinition
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LoopState:
    """State of the execution loop."""

    iteration: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    done: bool = False
    final_answer: str = ""


class ExecutionLoop:
    """Manages the LLM execution loop.

    Supports multiple strategies:
    - ReAct: Think → Act → Observe cycle
    - CoT: Chain of Thought
    - ToT: Tree of Thoughts
    """

    def __init__(self, config: ExecutionConfig, tool_registry: ToolRegistry) -> None:
        self.config = config
        self.tool_registry = tool_registry
        self._state = LoopState()

    def reset(self) -> None:
        """Reset the loop state."""
        self._state = LoopState()

    @property
    def state(self) -> LoopState:
        return self._state

    def should_continue(self) -> bool:
        """Check if the loop should continue."""
        return (
            not self._state.done
            and self._state.iteration < self.config.max_iterations
        )

    def record_thought(self, thought: str) -> None:
        """Record a thought in the loop state."""
        self._state.history.append({
            "type": "thought",
            "content": thought,
            "iteration": self._state.iteration,
        })

    def record_action(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Record an action (tool call) in the loop state."""
        self._state.tool_calls.append({
            "tool": tool_name,
            "arguments": arguments,
            "iteration": self._state.iteration,
        })

    def record_observation(self, observation: str) -> None:
        """Record an observation in the loop state."""
        self._state.observations.append(observation)
        self._state.history.append({
            "type": "observation",
            "content": observation,
            "iteration": self._state.iteration,
        })

    def set_done(self, final_answer: str) -> None:
        """Mark the loop as done with a final answer."""
        self._state.done = True
        self._state.final_answer = final_answer

    def increment(self) -> None:
        """Increment the iteration counter."""
        self._state.iteration += 1

    def build_loop_prompt(self, original_prompt: str) -> str:
        """Build a prompt that includes the current loop state."""
        parts = [original_prompt]

        if self._state.iteration > 0:
            parts.append(f"\n## Previous Steps (iteration {self._state.iteration})")

            for entry in self._state.history[-5:]:  # Last 5 entries
                if entry["type"] == "thought":
                    parts.append(f"\nThought: {entry['content']}")
                elif entry["type"] == "observation":
                    parts.append(f"\nObservation: {entry['content']}")

            if self._state.tool_calls:
                last_calls = self._state.tool_calls[-3:]
                parts.append("\n## Recent Tool Calls")
                for call in last_calls:
                    parts.append(f"- {call['tool']}({call['arguments']})")

        return "\n".join(parts)
