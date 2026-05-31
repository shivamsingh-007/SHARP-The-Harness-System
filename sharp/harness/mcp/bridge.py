"""MCP-to-Tool Bridge - converts MCP tools/resources/prompts to internal formats."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from sharp.harness.core.types import RiskLevel, ToolDefinition, ToolResult
from sharp.harness.context.sources import ContextSource
from sharp.harness.mcp.client import MCPClient
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)

# Risk assessment keywords
_READ_KEYWORDS = {"read", "get", "list", "search", "query", "fetch", "find", "view", "show", "describe"}
_WRITE_KEYWORDS = {"write", "create", "update", "put", "post", "modify", "edit", "set", "save", "store"}
_EXECUTE_KEYWORDS = {"execute", "run", "exec", "call", "invoke", "send", "submit", "process"}
_CRITICAL_KEYWORDS = {"delete", "drop", "remove", "destroy", "revoke", "terminate", "purge", "truncate"}


class MCPToToolBridge:
    """Bridges MCP primitives to the harness system's internal formats.

    Converts:
    - MCP Tools → ToolDefinition + callable wrapper (registered in ToolRegistry)
    - MCP Resources → ContextSource (fed to ContextCurator)
    - MCP Prompts → Prompt templates (registered in PromptTemplates)
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.mcp_client = mcp_client
        self.tool_registry = tool_registry
        self._registered_tools: dict[str, ToolDefinition] = {}

    async def register_all_tools(self) -> list[ToolDefinition]:
        """Discover all MCP tools and register them in the ToolRegistry.

        Returns list of registered ToolDefinitions.
        """
        if not self.tool_registry:
            logger.warning("No ToolRegistry provided, cannot register MCP tools")
            return []

        registered = []
        for tool_name, tool_data in self.mcp_client.discovered_tools.items():
            tool_def = self.to_tool_definition(tool_data)
            wrapper_fn = self._make_tool_fn(tool_name, tool_data["server"])

            self.tool_registry.register(wrapper_fn, tool_def)
            self._registered_tools[tool_name] = tool_def
            registered.append(tool_def)

            logger.info(f"Registered MCP tool: {tool_name} (risk: {tool_def.risk_level.value})")

        logger.info(f"Registered {len(registered)} MCP tools")
        return registered

    def to_tool_definition(self, mcp_tool: dict[str, Any]) -> ToolDefinition:
        """Convert an MCP tool dict to an internal ToolDefinition.

        Args:
            mcp_tool: Dict with keys: name, description, input_schema, server
        """
        name = mcp_tool["name"]
        description = mcp_tool.get("description", "")
        input_schema = mcp_tool.get("input_schema", {})

        # Assess risk level
        risk_level = self._assess_risk(name, description)

        return ToolDefinition(
            name=name,
            description=description,
            parameters=input_schema,
            risk_level=risk_level,
            requires_approval=risk_level in (RiskLevel.EXECUTE, RiskLevel.CRITICAL),
            timeout=30.0,
        )

    def _make_tool_fn(self, tool_name: str, server_name: str) -> Callable[..., Awaitable[str]]:
        """Create an async callable that wraps an MCP tool call.

        This function signature matches what ToolRegistry.execute() expects:
        async def fn(**arguments) -> result
        """
        async def mcp_tool_wrapper(**arguments: Any) -> str:
            result = await self.mcp_client.call_tool(tool_name, arguments)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("output", "")

        mcp_tool_wrapper.__name__ = tool_name
        mcp_tool_wrapper.__doc__ = f"MCP tool from server '{server_name}'"
        return mcp_tool_wrapper

    def _assess_risk(self, tool_name: str, description: str = "") -> RiskLevel:
        """Assess risk level of an MCP tool based on its name and description.

        Heuristic-based classification:
        - read/get/list/search → READ
        - write/create/update → WRITE
        - execute/run/call → EXECUTE
        - delete/drop/remove → CRITICAL
        """
        name_lower = tool_name.lower()
        desc_lower = description.lower()
        combined = f"{name_lower} {desc_lower}"

        # Check for overrides first
        # (overrides are applied at config level, checked before this)

        # Check critical first (most dangerous)
        if any(kw in name_lower for kw in _CRITICAL_KEYWORDS):
            return RiskLevel.CRITICAL

        # Check execute
        if any(kw in name_lower for kw in _EXECUTE_KEYWORDS):
            return RiskLevel.EXECUTE

        # Check write
        if any(kw in name_lower for kw in _WRITE_KEYWORDS):
            return RiskLevel.WRITE

        # Check read (default for most tools)
        if any(kw in name_lower for kw in _READ_KEYWORDS):
            return RiskLevel.READ

        # Default to READ for unknown tools
        return RiskLevel.READ

    def get_context_from_resources(self) -> list[ContextSource]:
        """Convert discovered MCP resources into ContextSource objects.

        This feeds MCP resources into the Context Engineering Zone.
        Resources are treated as retrieved documents.
        """
        sources = []

        for uri, resource_data in self.mcp_client.discovered_resources.items():
            # Skip templates (they have parameters, need to be read explicitly)
            if "uri_template" in resource_data:
                continue

            source = ContextSource(
                name=f"mcp:{resource_data.get('name', uri)}",
                content=f"[MCP Resource: {uri}] {resource_data.get('description', '')}",
                source_type="retrieved_doc",
                priority=3,  # Lower priority than user/memory/tool_output
                metadata={
                    "mcp_uri": uri,
                    "mcp_server": resource_data.get("server", ""),
                    "mcp_mime_type": resource_data.get("mime_type", ""),
                },
            )
            sources.append(source)

        if sources:
            logger.info(f"Generated {len(sources)} context sources from MCP resources")

        return sources

    def get_prompt_templates(self) -> dict[str, dict[str, Any]]:
        """Get MCP prompts as template definitions.

        Returns dict of prompt_name -> template data for PromptTemplates.
        """
        templates = {}

        for prompt_name, prompt_data in self.mcp_client.discovered_prompts.items():
            templates[prompt_name] = {
                "name": prompt_name,
                "description": prompt_data.get("description", ""),
                "arguments": prompt_data.get("arguments", []),
                "server": prompt_data.get("server", ""),
            }

        return templates

    async def apply_risk_overrides(self, overrides: dict[str, str]) -> None:
        """Apply user-defined risk level overrides to registered tools.

        Args:
            overrides: dict of tool_name -> risk_level_string
        """
        for tool_name, risk_str in overrides.items():
            if tool_name in self._registered_tools:
                try:
                    risk_level = RiskLevel(risk_str)
                    self._registered_tools[tool_name].risk_level = risk_level
                    self._registered_tools[tool_name].requires_approval = (
                        risk_level in (RiskLevel.EXECUTE, RiskLevel.CRITICAL)
                    )
                    logger.info(f"Override risk for '{tool_name}': {risk_level.value}")
                except ValueError:
                    logger.warning(f"Invalid risk level '{risk_str}' for tool '{tool_name}'")

    def get_registered_tools(self) -> list[ToolDefinition]:
        """Get all registered MCP tool definitions."""
        return list(self._registered_tools.values())
