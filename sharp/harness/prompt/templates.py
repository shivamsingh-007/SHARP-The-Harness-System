"""System prompt templates."""

from __future__ import annotations

from dataclasses import dataclass

from sharp.harness.core.types import ToolDefinition


DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant powered by the Harness System.

## Instructions
- Think step by step before answering
- Use available tools when they can help answer the question
- Provide clear, concise, and accurate responses
- If you're unsure, say so rather than guessing
- Follow the user's instructions carefully

{memory_section}
{context_section}
{tools_section}
{constraints_section}
"""

TOOL_DESCRIPTION_TEMPLATE = """
### Tool: {name}
{description}
Parameters: {parameters}
Risk Level: {risk_level}
"""

CONSTRAINTS_TEMPLATE = """
## Constraints
- Stay within the provided context
- Do not make up information not present in the context
- If a tool fails, explain why and suggest alternatives
- Validate your response before presenting it
"""


@dataclass
class PromptTemplate:
    """A customizable prompt template."""

    system: str = DEFAULT_SYSTEM_PROMPT
    include_memory: bool = True
    include_context: bool = True
    include_tools: bool = True
    include_constraints: bool = True
    custom_sections: dict[str, str] | None = None


class PromptTemplates:
    """Manages prompt templates for the harness system."""

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {
            "default": PromptTemplate(),
        }

    def get_template(self, name: str = "default") -> PromptTemplate:
        """Get a prompt template by name."""
        return self._templates.get(name, self._templates["default"])

    def register(self, name: str, template: PromptTemplate) -> None:
        """Register a custom prompt template."""
        self._templates[name] = template

    def render_system_prompt(
        self,
        template_name: str = "default",
        memory: str = "",
        context: str = "",
        tools: list[ToolDefinition] | None = None,
        constraints: str = "",
    ) -> str:
        """Render a system prompt from a template."""
        template = self.get_template(template_name)

        sections = {}

        # Memory section
        if template.include_memory and memory:
            sections["memory_section"] = f"## Memory\n{memory}"
        else:
            sections["memory_section"] = ""

        # Context section
        if template.include_context and context:
            sections["context_section"] = f"## Context\n{context}"
        else:
            sections["context_section"] = ""

        # Tools section
        if template.include_tools and tools:
            tool_descriptions = []
            for tool in tools:
                tool_descriptions.append(
                    TOOL_DESCRIPTION_TEMPLATE.format(
                        name=tool.name,
                        description=tool.description,
                        parameters=tool.parameters,
                        risk_level=tool.risk_level.value,
                    )
                )
            sections["tools_section"] = "## Available Tools\n" + "\n".join(tool_descriptions)
        else:
            sections["tools_section"] = ""

        # Constraints section
        if template.include_constraints:
            sections["constraints_section"] = constraints or CONSTRAINTS_TEMPLATE
        else:
            sections["constraints_section"] = ""

        # Custom sections
        if template.custom_sections:
            for key, value in template.custom_sections.items():
                sections[key] = value

        return template.system.format(**sections)
