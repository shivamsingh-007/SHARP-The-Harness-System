"""Execution loop - ReAct/CoT/ToT execution strategies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sharp.harness.core.config import ExecutionConfig
from sharp.harness.core.types import LoopStrategy, ToolDefinition
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)

REACT_SYSTEM_PROMPT = """You are an intelligent agent that solves tasks step by step.

You have access to the following tools:
{tools_description}

## Execution Strategy: {strategy}

For each step, you must output EXACTLY one of:
1. **Thought**: Your reasoning about what to do next
2. **Action**: A tool call in the format: Action: tool_name(arg1="value1", arg2="value2")
3. **Observation**: (This is provided by the system after each Action)
4. **Final Answer**: Your complete response when done

### Format Example:
Thought: I need to find information about X
Action: search(query="X details")
Observation: [system provides result]
Thought: Now I have the information, let me formulate the answer
Final Answer: [your complete answer]

Important:
- Always start with a Thought
- Only ONE Action per step
- Wait for Observation before proceeding
- End with Final Answer when you have enough information
- Do not repeat the same action
"""


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
    - ReAct: Think -> Act -> Observe cycle
    - CoT: Chain of Thought (linear reasoning)
    - ToT: Tree of Thoughts (parallel exploration)
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

            for entry in self._state.history[-5:]:
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

    def _build_tools_description(self, tools: list[ToolDefinition]) -> str:
        """Build a description of available tools for the system prompt."""
        if not tools:
            return "No tools available."

        lines = []
        for tool in tools:
            params = tool.parameters or {"type": "object", "properties": {}}
            props = params.get("properties", {})
            param_str = ", ".join(f'{k}: {v.get("type", "any")}' for k, v in props.items())
            lines.append(f"- {tool.name}({param_str}): {tool.description}")
        return "\n".join(lines)

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        """Parse the LLM response into thought/action/final_answer."""
        content = content.strip()

        # Check for Final Answer
        final_match = re.search(
            r'Final\s+Answer\s*:\s*(.+?)(?:\n|$)', content, re.IGNORECASE | re.DOTALL
        )
        if final_match:
            return {"type": "final_answer", "content": final_match.group(1).strip()}

        # Check for Action
        action_match = re.search(
            r'Action\s*:\s*(\w+)\s*\((.*?)\)', content, re.DOTALL
        )
        if action_match:
            tool_name = action_match.group(1)
            args_str = action_match.group(2)
            arguments = self._parse_action_args(args_str)
            return {"type": "action", "tool": tool_name, "arguments": arguments}

        # Check for Thought
        thought_match = re.search(r'Thought\s*:\s*(.+?)(?:\nAction|\nFinal|\Z)', content, re.DOTALL)
        if thought_match:
            return {"type": "thought", "content": thought_match.group(1).strip()}

        # If content exists but no structured format:
        # On iteration 1 with no tools used yet, treat as final answer
        if content and self._state.iteration > 1 and not self._state.tool_calls:
            return {"type": "final_answer", "content": content}

        if content:
            return {"type": "thought", "content": content}

        return {"type": "thought", "content": ""}

    def _parse_action_args(self, args_str: str) -> dict[str, Any]:
        """Parse action arguments from string format."""
        args = {}
        if not args_str.strip():
            return args

        # Simple key="value" parsing
        for match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', args_str):
            args[match.group(1)] = match.group(2)

        # Also handle key='value' and bare values
        for match in re.finditer(r"(\w+)\s*=\s*'([^']*)'", args_str):
            if match.group(1) not in args:
                args[match.group(1)] = match.group(2)

        # Handle numeric/boolean bare values
        for match in re.finditer(r'(\w+)\s*=\s*(\d+\.?\d*|true|false|null)', args_str):
            if match.group(1) not in args:
                val = match.group(2)
                if val == "true":
                    args[match.group(1)] = True
                elif val == "false":
                    args[match.group(1)] = False
                elif val == "null":
                    args[match.group(1)] = None
                else:
                    try:
                        args[match.group(1)] = float(val) if "." in val else int(val)
                    except ValueError:
                        args[match.group(1)] = val

        return args

    async def run(
        self,
        provider: Any,
        user_request: str,
        tools: list[ToolDefinition] | None = None,
        system_prompt: str = "",
    ) -> str:
        """Execute the ReAct/CoT/ToT loop.

        Args:
            provider: LLMProvider instance for making LLM calls.
            user_request: The original user request.
            tools: Available tool definitions.
            system_prompt: Base system prompt.

        Returns:
            The final answer from the loop.
        """
        self.reset()
        tools = tools or []
        strategy = self.config.loop_strategy

        # Build the system prompt with tool descriptions
        tools_desc = self._build_tools_description(tools)
        loop_system = REACT_SYSTEM_PROMPT.format(
            tools_description=tools_desc,
            strategy=strategy.value.upper(),
        )

        if system_prompt:
            loop_system = f"{system_prompt}\n\n{loop_system}"

        logger.info(f"Starting {strategy.value} loop (max {self.config.max_iterations} iterations)")

        while self.should_continue():
            self.increment()

            # Build the prompt with loop state
            loop_prompt = self.build_loop_prompt(user_request)

            # Call LLM
            try:
                response = await provider.complete(
                    system_prompt=loop_system,
                    user_message=loop_prompt,
                    tools=tools if tools else None,
                )
                content = response.content
            except Exception as e:
                logger.error(f"LLM call failed in loop iteration {self._state.iteration}: {e}")
                self.record_observation(f"Error: {e}")
                continue

            # Parse response
            parsed = self._parse_llm_response(content)

            if parsed["type"] == "final_answer":
                self.set_done(parsed["content"])
                logger.info(f"Loop completed with final answer at iteration {self._state.iteration}")
                break

            elif parsed["type"] == "action":
                tool_name = parsed["tool"]
                arguments = parsed["arguments"]
                self.record_action(tool_name, arguments)

                # Execute tool
                tool_result = await self.tool_registry.execute(tool_name, arguments)
                observation = tool_result.output if tool_result.success else f"Error: {tool_result.error}"
                self.record_observation(observation)

                logger.info(
                    f"Iteration {self._state.iteration}: {tool_name} -> "
                    f"{'OK' if tool_result.success else 'FAILED'}"
                )

            elif parsed["type"] == "thought":
                self.record_thought(parsed["content"])
                logger.debug(f"Iteration {self._state.iteration}: Thought recorded")

        if not self._state.done:
            logger.warning(f"Loop ended without final answer after {self._state.iteration} iterations")
            # Return whatever we have
            if self._state.observations:
                return self._state.observations[-1]
            return "Loop completed without a final answer."

        return self._state.final_answer
