"""Prompt composer - assembles augmented prompt from context."""

from __future__ import annotations

from dataclasses import dataclass, field

from sharp.harness.core.config import PromptConfig
from sharp.harness.core.types import ToolDefinition
from sharp.harness.context.sources import ContextSource
from sharp.harness.prompt.budget import TokenBudget
from sharp.harness.prompt.templates import PromptTemplates
from sharp.harness.utils.tokens import count_tokens
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AugmentedPrompt:
    """The final assembled prompt ready for LLM consumption."""

    system_prompt: str
    user_message: str
    context_summary: str
    total_tokens: int = 0
    sections: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.total_tokens = count_tokens(self.system_prompt) + count_tokens(self.user_message)


class PromptComposer:
    """Assembles augmented prompts from context sources.

    Combines:
    - System prompt template
    - Curated context (memory, docs, tool outputs)
    - Tool descriptions
    - User request
    """

    def __init__(self, config: PromptConfig) -> None:
        self.config = config
        self.templates = PromptTemplates()
        self.budget = TokenBudget(
            total_budget=config.max_context_tokens + config.reserved_output_tokens,
            reserved_output=config.reserved_output_tokens,
        )

    def compose(
        self,
        user_request: str,
        context_sources: list[ContextSource] | None = None,
        tools: list[ToolDefinition] | None = None,
        template_name: str | None = None,
    ) -> AugmentedPrompt:
        """Compose an augmented prompt from context sources.

        Returns an AugmentedPrompt with system prompt and user message.
        """
        logger.info("Composing augmented prompt")

        # Separate context by type
        memory_parts = []
        context_parts = []
        tool_output_parts = []

        if context_sources:
            for source in context_sources:
                if source.source_type == "memory":
                    memory_parts.append(f"### {source.name}\n{source.content}")
                elif source.source_type == "user":
                    pass  # User request goes to user_message
                elif source.source_type == "tool_output":
                    tool_output_parts.append(f"### {source.name}\n{source.content}")
                else:
                    context_parts.append(f"### {source.name}\n{source.content}")

        # Build context summary
        context_summary_parts = []
        if memory_parts:
            context_summary_parts.append("## Memory\n" + "\n\n".join(memory_parts))
        if context_parts:
            context_summary_parts.append("## Retrieved Context\n" + "\n\n".join(context_parts))
        if tool_output_parts:
            context_summary_parts.append("## Prior Tool Outputs\n" + "\n\n".join(tool_output_parts))

        context_summary = "\n\n".join(context_summary_parts)

        # Apply token budget to context
        if context_summary:
            context_summary = self.budget.allocate_for_content("context", context_summary)

        # Render system prompt
        tpl_name = template_name or self.config.system_prompt_template
        system_prompt = self.templates.render_system_prompt(
            template_name=tpl_name,
            memory="\n\n".join(memory_parts) if memory_parts else "",
            context=context_summary,
            tools=tools if self.config.include_tools_in_prompt else None,
        )

        # Allocate system prompt budget
        system_prompt = self.budget.allocate_for_content("system_prompt", system_prompt)

        # Build user message
        user_message = user_request

        # Track section sizes
        sections = {
            "system_prompt": count_tokens(system_prompt),
            "user_message": count_tokens(user_message),
            "context": count_tokens(context_summary),
        }

        logger.info(f"Prompt composed: {sections}")

        return AugmentedPrompt(
            system_prompt=system_prompt,
            user_message=user_message,
            context_summary=context_summary,
            sections=sections,
        )
