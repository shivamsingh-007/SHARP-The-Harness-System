"""Sub-agent manager - spawning and orchestrating sub-agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubAgentDefinition:
    """Definition of a sub-agent."""

    name: str
    role: str
    instructions: str
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 5


@dataclass
class SubAgentResult:
    """Result from a sub-agent execution."""

    agent_name: str
    task: str
    output: str
    success: bool = True
    iterations_used: int = 0
    error: str = ""


class SubAgentManager:
    """Manages sub-agent spawning and orchestration.

    Sub-agents are specialized agents that handle specific tasks
    delegated by the main agent. Each sub-agent gets its own LLM
    conversation with role-specific instructions.
    """

    def __init__(self) -> None:
        self._agents: dict[str, SubAgentDefinition] = {}
        self._active: dict[str, Any] = {}
        self._results: dict[str, SubAgentResult] = {}

    def register(self, definition: SubAgentDefinition) -> None:
        """Register a sub-agent definition."""
        self._agents[definition.name] = definition
        logger.info(f"Registered sub-agent: {definition.name}")

    def get(self, name: str) -> SubAgentDefinition | None:
        """Get a sub-agent definition by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[SubAgentDefinition]:
        """List all registered sub-agents."""
        return list(self._agents.values())

    async def spawn(
        self,
        name: str,
        task: str,
        provider: Any,
        context: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
    ) -> SubAgentResult:
        """Spawn a sub-agent to handle a task using an LLM provider.

        Args:
            name: Name of the sub-agent to spawn.
            task: The task for the sub-agent to perform.
            provider: LLMProvider instance for making LLM calls.
            context: Additional context for the sub-agent.
            tools: Optional tool definitions available to the sub-agent.

        Returns:
            SubAgentResult with the sub-agent's response.
        """
        definition = self._agents.get(name)
        if not definition:
            return SubAgentResult(
                agent_name=name,
                task=task,
                output=f"Sub-agent '{name}' not found",
                success=False,
                error=f"Sub-agent '{name}' not registered",
            )

        logger.info(f"Spawning sub-agent '{name}' for task: {task[:100]}...")

        # Build system prompt for sub-agent
        system_prompt = f"""You are {definition.name}, a {definition.role}.

{definition.instructions}

You are a specialized sub-agent. Complete the task efficiently and provide a clear, concise result.
Output your final answer after reasoning through the problem step by step."""

        # Build user message with context
        user_message = f"Task: {task}"
        if context:
            user_message += f"\n\nContext:\n{str(context)}"

        # Execute with the LLM provider
        try:
            response = await provider.complete(
                system_prompt=system_prompt,
                user_message=user_message,
                tools=tools,
            )

            result = SubAgentResult(
                agent_name=name,
                task=task,
                output=response.content,
                success=True,
                iterations_used=1,
            )

            self._results[name] = result
            logger.info(f"Sub-agent '{name}' completed task successfully")
            return result

        except Exception as e:
            logger.error(f"Sub-agent '{name}' failed: {e}")
            result = SubAgentResult(
                agent_name=name,
                task=task,
                output="",
                success=False,
                error=str(e),
            )
            self._results[name] = result
            return result

    def get_result(self, name: str) -> SubAgentResult | None:
        """Get the last result from a sub-agent."""
        return self._results.get(name)

    def deactivate(self, name: str) -> None:
        """Deactivate a sub-agent."""
        self._active.pop(name, None)
