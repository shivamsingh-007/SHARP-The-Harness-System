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


class SubAgentManager:
    """Manages sub-agent spawning and orchestration.

    Sub-agents are specialized agents that handle specific tasks
    delegated by the main agent.
    """

    def __init__(self) -> None:
        self._agents: dict[str, SubAgentDefinition] = {}
        self._active: dict[str, Any] = {}

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
        context: dict[str, Any] | None = None,
    ) -> str:
        """Spawn a sub-agent to handle a task.

        Args:
            name: Name of the sub-agent to spawn.
            task: The task for the sub-agent to perform.
            context: Additional context for the sub-agent.

        Returns:
            The sub-agent's response.
        """
        definition = self._agents.get(name)
        if not definition:
            return f"Sub-agent '{name}' not found"

        logger.info(f"Spawning sub-agent '{name}' for task: {task[:100]}...")

        # Build prompt for sub-agent
        prompt = f"""You are {definition.name}, a {definition.role}.

{definition.instructions}

Task: {task}
"""
        if context:
            prompt += f"\nContext: {context}"

        # Execute sub-agent (simplified - in production, use LLMProvider)
        # This is a placeholder for the actual sub-agent execution
        return f"[Sub-agent '{name}' completed task]"

    def deactivate(self, name: str) -> None:
        """Deactivate a sub-agent."""
        self._active.pop(name, None)
