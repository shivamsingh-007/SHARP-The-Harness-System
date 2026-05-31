"""Token budget allocator for prompt construction."""

from __future__ import annotations

from dataclasses import dataclass, field

from sharp.harness.utils.tokens import count_tokens


@dataclass
class BudgetAllocation:
    """Allocation of token budget across prompt sections."""

    system_prompt: int = 2000
    context: int = 4000
    tools: int = 1000
    conversation: int = 1000
    reserved_output: int = 2000

    @property
    def total(self) -> int:
        return (
            self.system_prompt
            + self.context
            + self.tools
            + self.conversation
            + self.reserved_output
        )


class TokenBudget:
    """Manages token budget allocation for prompt construction.

    Ensures the total prompt stays within the model's context window
    by allocating appropriate budgets to each section.
    """

    def __init__(
        self,
        total_budget: int = 8000,
        reserved_output: int = 2000,
        system_ratio: float = 0.25,
        context_ratio: float = 0.50,
        tools_ratio: float = 0.125,
        conversation_ratio: float = 0.125,
    ) -> None:
        available = total_budget - reserved_output
        self.allocation = BudgetAllocation(
            system_prompt=int(available * system_ratio),
            context=int(available * context_ratio),
            tools=int(available * tools_ratio),
            conversation=int(available * conversation_ratio),
            reserved_output=reserved_output,
        )

    def allocate_for_content(self, section: str, content: str) -> str:
        """Truncate content to fit within its budget allocation."""
        budget = getattr(self.allocation, section, 0)
        tokens = count_tokens(content)
        if tokens <= budget:
            return content
        from sharp.harness.utils.tokens import truncate_to_tokens
        return truncate_to_tokens(content, budget)

    def get_available(self, section: str) -> int:
        """Get available tokens for a section."""
        return getattr(self.allocation, section, 0)

    def report(self) -> dict[str, int]:
        """Get budget allocation report."""
        return {
            "system_prompt": self.allocation.system_prompt,
            "context": self.allocation.context,
            "tools": self.allocation.tools,
            "conversation": self.allocation.conversation,
            "reserved_output": self.allocation.reserved_output,
            "total": self.allocation.total,
        }
