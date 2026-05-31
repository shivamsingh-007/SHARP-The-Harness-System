"""MCP Client - Host that connects to MCP servers via stdio or HTTP."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sharp.harness.core.config import MCPConfig, MCPServerConfig
from sharp.harness.mcp.registry import MCPServer, MCPRegistry
from sharp.harness.observability.logging import get_logger
from sharp.harness.observability.telemetry import TelemetryCollector

logger = get_logger(__name__)


class MCPClient:
    """MCP Host Client that connects to multiple MCP servers.

    Manages connections via stdio or HTTP/SSE transports,
    discovers tools/resources/prompts, and routes calls.
    """

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self.registry = MCPRegistry()
        self._sessions: dict[str, Any] = {}  # server_name -> ClientSession
        self._read_streams: dict[str, Any] = {}
        self._write_streams: dict[str, Any] = {}
        self._exit_stacks: dict[str, Any] = {}
        self._tool_server_map: dict[str, str] = {}  # tool_name -> server_name
        self._resource_server_map: dict[str, str] = {}  # resource_uri -> server_name
        self._prompt_server_map: dict[str, str] = {}  # prompt_name -> server_name
        self._discovered_tools: dict[str, dict[str, Any]] = {}
        self._discovered_resources: dict[str, dict[str, Any]] = {}
        self._discovered_prompts: dict[str, dict[str, Any]] = {}
        self._connected: set[str] = set()
        self._telemetry = TelemetryCollector()

    @property
    def connected_servers(self) -> list[str]:
        """List of connected server names."""
        return list(self._connected)

    @property
    def discovered_tools(self) -> dict[str, dict[str, Any]]:
        """All discovered tools across servers."""
        return self._discovered_tools.copy()

    @property
    def discovered_resources(self) -> dict[str, dict[str, Any]]:
        """All discovered resources across servers."""
        return self._discovered_resources.copy()

    @property
    def discovered_prompts(self) -> dict[str, dict[str, Any]]:
        """All discovered prompts across servers."""
        return self._discovered_prompts.copy()

    async def connect_stdio(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Connect to an MCP server via stdio transport.

        Args:
            name: Server name identifier.
            command: Command to run (e.g., "npx", "python").
            args: Command arguments.
            env: Environment variables.
        """
        if name in self._connected:
            logger.warning(f"MCP server '{name}' already connected")
            return

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise ImportError(
                "MCP SDK not installed. Install with: pip install 'mcp>=1.20'"
            )

        server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env,
        )

        logger.info(f"Connecting to MCP server '{name}' via stdio: {command} {' '.join(args or [])}")

        try:
            # Create the connection context managers
            stdio_ctx = stdio_client(server_params)
            read_stream, write_stream = await stdio_ctx.__aenter__()

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            self._sessions[name] = session
            self._read_streams[name] = read_stream
            self._write_streams[name] = write_stream
            self._exit_stacks[name] = stdio_ctx
            self._connected.add(name)

            # Discover capabilities
            await self._discover_capabilities(name)

            self._telemetry.emit("mcp.connected", data={"server": name, "transport": "stdio"})
            logger.info(f"Connected to MCP server '{name}' via stdio")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            self._telemetry.emit("mcp.connection_failed", data={"server": name, "error": str(e)})
            raise

    async def connect_http(
        self,
        name: str,
        url: str,
    ) -> None:
        """Connect to an MCP server via HTTP/SSE transport.

        Args:
            name: Server name identifier.
            url: Server URL (e.g., "http://localhost:8000/mcp").
        """
        if name in self._connected:
            logger.warning(f"MCP server '{name}' already connected")
            return

        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            raise ImportError(
                "MCP SDK not installed. Install with: pip install 'mcp>=1.20'"
            )

        logger.info(f"Connecting to MCP server '{name}' via HTTP: {url}")

        try:
            http_ctx = streamable_http_client(url)
            read_stream, write_stream, _ = await http_ctx.__aenter__()

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            self._sessions[name] = session
            self._read_streams[name] = read_stream
            self._write_streams[name] = write_stream
            self._exit_stacks[name] = http_ctx
            self._connected.add(name)

            # Discover capabilities
            await self._discover_capabilities(name)

            self._telemetry.emit("mcp.connected", data={"server": name, "transport": "http"})
            logger.info(f"Connected to MCP server '{name}' via HTTP")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            self._telemetry.emit("mcp.connection_failed", data={"server": name, "error": str(e)})
            raise

    async def connect_from_config(self, server_config: MCPServerConfig) -> None:
        """Connect using a MCPServerConfig."""
        if server_config.transport == "http":
            if not server_config.url:
                raise ValueError(f"Server '{server_config.name}' requires 'url' for HTTP transport")
            await self.connect_http(server_config.name, server_config.url)
        else:
            if not server_config.command:
                raise ValueError(f"Server '{server_config.name}' requires 'command' for stdio transport")
            await self.connect_stdio(
                server_config.name,
                server_config.command,
                server_config.args,
                server_config.env,
            )

    async def disconnect(self, name: str) -> None:
        """Disconnect from an MCP server."""
        if name not in self._connected:
            return

        logger.info(f"Disconnecting from MCP server '{name}'")

        try:
            session = self._sessions.pop(name, None)
            if session:
                await session.__aexit__(None, None, None)

            exit_stack = self._exit_stacks.pop(name, None)
            if exit_stack:
                await exit_stack.__aexit__(None, None, None)

            self._read_streams.pop(name, None)
            self._write_streams.pop(name, None)
            self._connected.discard(name)

            # Remove tool/resource/prompt mappings for this server
            self._tool_server_map = {
                k: v for k, v in self._tool_server_map.items() if v != name
            }
            self._resource_server_map = {
                k: v for k, v in self._resource_server_map.items() if v != name
            }
            self._prompt_server_map = {
                k: v for k, v in self._prompt_server_map.items() if v != name
            }

            # Remove discovered items from this server
            self._discovered_tools = {
                k: v for k, v in self._discovered_tools.items()
                if v.get("server") != name
            }
            self._discovered_resources = {
                k: v for k, v in self._discovered_resources.items()
                if v.get("server") != name
            }
            self._discovered_prompts = {
                k: v for k, v in self._discovered_prompts.items()
                if v.get("server") != name
            }

            self._telemetry.emit("mcp.disconnected", data={"server": name})
            logger.info(f"Disconnected from MCP server '{name}'")

        except Exception as e:
            logger.error(f"Error disconnecting from '{name}': {e}")

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for name in list(self._connected):
            await self.disconnect(name)

    async def _discover_capabilities(self, server_name: str) -> None:
        """Discover tools, resources, and prompts from a connected server."""
        session = self._sessions.get(server_name)
        if not session:
            return

        logger.info(f"Discovering capabilities from '{server_name}'")

        # Discover tools
        try:
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                tool_data = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": _schema_to_dict(tool.inputSchema) if tool.inputSchema else {},
                    "server": server_name,
                }
                self._discovered_tools[tool.name] = tool_data
                self._tool_server_map[tool.name] = server_name
                logger.debug(f"  Discovered tool: {tool.name}")
        except Exception as e:
            logger.warning(f"Failed to list tools from '{server_name}': {e}")

        # Discover resources
        try:
            resources_result = await session.list_resources()
            for resource in resources_result.resources:
                uri = str(resource.uri) if resource.uri else ""
                resource_data = {
                    "name": resource.name,
                    "uri": uri,
                    "description": resource.description or "",
                    "mime_type": resource.mimeType or "",
                    "server": server_name,
                }
                self._discovered_resources[uri] = resource_data
                self._resource_server_map[uri] = server_name
                logger.debug(f"  Discovered resource: {uri}")
        except Exception as e:
            logger.warning(f"Failed to list resources from '{server_name}': {e}")

        # Discover resource templates
        try:
            templates_result = await session.list_resource_templates()
            for template in templates_result.resourceTemplates:
                uri_template = template.uriTemplate or ""
                template_data = {
                    "name": uri_template,
                    "uri_template": uri_template,
                    "description": template.description or "",
                    "server": server_name,
                }
                self._discovered_resources[uri_template] = template_data
                self._resource_server_map[uri_template] = server_name
                logger.debug(f"  Discovered resource template: {uri_template}")
        except Exception as e:
            logger.warning(f"Failed to list resource templates from '{server_name}': {e}")

        # Discover prompts
        try:
            prompts_result = await session.list_prompts()
            for prompt in prompts_result.prompts:
                prompt_data = {
                    "name": prompt.name,
                    "description": prompt.description or "",
                    "arguments": [
                        {"name": arg.name, "description": arg.description or "", "required": arg.required}
                        for arg in (prompt.arguments or [])
                    ],
                    "server": server_name,
                }
                self._discovered_prompts[prompt.name] = prompt_data
                self._prompt_server_map[prompt.name] = server_name
                logger.debug(f"  Discovered prompt: {prompt.name}")
        except Exception as e:
            logger.warning(f"Failed to list prompts from '{server_name}': {e}")

        tools_count = sum(1 for t in self._discovered_tools.values() if t["server"] == server_name)
        resources_count = sum(1 for r in self._discovered_resources.values() if r["server"] == server_name)
        prompts_count = sum(1 for p in self._discovered_prompts.values() if p["server"] == server_name)

        logger.info(
            f"Discovered from '{server_name}': "
            f"{tools_count} tools, {resources_count} resources, {prompts_count} prompts"
        )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool by name.

        Routes to the correct server based on discovery mapping.
        """
        server_name = self._tool_server_map.get(tool_name)
        if not server_name:
            return {"error": f"Tool '{tool_name}' not found in any connected server"}

        session = self._sessions.get(server_name)
        if not session:
            return {"error": f"Server '{server_name}' not connected"}

        logger.info(f"Calling MCP tool '{tool_name}' on server '{server_name}'")
        self._telemetry.emit(
            "mcp.tool_call",
            data={"tool": tool_name, "server": server_name, "arguments": arguments},
        )

        try:
            result = await session.call_tool(tool_name, arguments=arguments)

            # Parse the result content
            output_parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    output_parts.append(content.text)
                elif hasattr(content, "data"):
                    output_parts.append(f"[{content.mimeType}] {content.data[:100]}...")
                else:
                    output_parts.append(str(content))

            output = "\n".join(output_parts) if output_parts else ""

            return {
                "success": not result.isError if hasattr(result, "isError") else True,
                "output": output,
                "tool_name": tool_name,
                "server": server_name,
                "is_error": getattr(result, "isError", False),
            }

        except Exception as e:
            logger.error(f"MCP tool '{tool_name}' failed: {e}")
            return {"error": str(e), "tool_name": tool_name, "server": server_name}

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read an MCP resource by URI.

        Routes to the correct server based on discovery mapping.
        """
        server_name = self._resource_server_map.get(uri)
        if not server_name:
            return {"error": f"Resource '{uri}' not found in any connected server"}

        session = self._sessions.get(server_name)
        if not session:
            return {"error": f"Server '{server_name}' not connected"}

        logger.info(f"Reading MCP resource '{uri}' from server '{server_name}'")
        self._telemetry.emit("mcp.resource_read", data={"uri": uri, "server": server_name})

        try:
            from pydantic import AnyUrl
            result = await session.read_resource(AnyUrl(uri))

            contents = []
            for content in result.contents:
                if hasattr(content, "text"):
                    contents.append({
                        "text": content.text,
                        "uri": str(content.uri) if hasattr(content, "uri") else uri,
                        "mime_type": getattr(content, "mimeType", ""),
                    })
                elif hasattr(content, "data"):
                    contents.append({
                        "data": content.data,
                        "uri": str(content.uri) if hasattr(content, "uri") else uri,
                        "mime_type": getattr(content, "mimeType", ""),
                    })

            return {
                "success": True,
                "contents": contents,
                "uri": uri,
                "server": server_name,
            }

        except Exception as e:
            logger.error(f"MCP resource '{uri}' read failed: {e}")
            return {"error": str(e), "uri": uri, "server": server_name}

    async def get_prompt(self, prompt_name: str, arguments: dict[str, str] | None = None) -> dict[str, Any]:
        """Get an MCP prompt with resolved arguments."""
        server_name = self._prompt_server_map.get(prompt_name)
        if not server_name:
            return {"error": f"Prompt '{prompt_name}' not found in any connected server"}

        session = self._sessions.get(server_name)
        if not session:
            return {"error": f"Server '{server_name}' not connected"}

        logger.info(f"Getting MCP prompt '{prompt_name}' from server '{server_name}'")

        try:
            result = await session.get_prompt(prompt_name, arguments=arguments or {})

            messages = []
            for msg in result.messages:
                content_text = ""
                if hasattr(msg.content, "text"):
                    content_text = msg.content.text
                elif isinstance(msg.content, list):
                    content_text = " ".join(
                        c.text if hasattr(c, "text") else str(c)
                        for c in msg.content
                    )
                else:
                    content_text = str(msg.content)

                messages.append({
                    "role": getattr(msg, "role", "user"),
                    "content": content_text,
                })

            return {
                "success": True,
                "messages": messages,
                "prompt_name": prompt_name,
                "server": server_name,
            }

        except Exception as e:
            logger.error(f"MCP prompt '{prompt_name}' failed: {e}")
            return {"error": str(e), "prompt_name": prompt_name, "server": server_name}

    def get_tools_for_server(self, server_name: str) -> list[dict[str, Any]]:
        """Get all tools from a specific server."""
        return [
            tool for tool in self._discovered_tools.values()
            if tool["server"] == server_name
        ]

    def get_all_tools_flat(self) -> list[dict[str, Any]]:
        """Get all discovered tools as a flat list."""
        return list(self._discovered_tools.values())


def _schema_to_dict(schema: Any) -> dict[str, Any]:
    """Convert an MCP schema object to a dict."""
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_dump"):
        return schema.model_dump()
    if hasattr(schema, "dict"):
        return schema.dict()
    try:
        return json.loads(json.dumps(schema, default=str))
    except Exception:
        return {}
