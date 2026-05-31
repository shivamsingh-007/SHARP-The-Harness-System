"""MCP Server Registry - manages MCP server definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MCPServer:
    """Definition of an MCP server connection."""

    name: str
    command: str | None = None  # for stdio (e.g., "npx", "python")
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None  # for http/sse
    transport: str = "stdio"  # "stdio" | "http"
    enabled: bool = True
    description: str = ""


# Default MCP servers available out of the box
DEFAULT_MCP_SERVERS: list[MCPServer] = [
    MCPServer(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "./"],
        transport="stdio",
        enabled=False,
        description="Read/write local filesystem files",
    ),
    MCPServer(
        name="github",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        transport="stdio",
        enabled=False,
        description="GitHub API access (repos, issues, PRs)",
    ),
    MCPServer(
        name="postgres",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        transport="stdio",
        enabled=False,
        description="PostgreSQL database access",
    ),
]


class MCPRegistry:
    """Registry of MCP server configurations.

    Manages server definitions and provides lookup capabilities.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServer] = {}

    def register(self, server: MCPServer) -> None:
        """Register an MCP server."""
        self._servers[server.name] = server
        logger.info(f"Registered MCP server: {server.name} ({server.transport})")

    def unregister(self, name: str) -> bool:
        """Unregister an MCP server."""
        if name in self._servers:
            del self._servers[name]
            logger.info(f"Unregistered MCP server: {name}")
            return True
        return False

    def get(self, name: str) -> MCPServer | None:
        """Get a server by name."""
        return self._servers.get(name)

    def get_enabled_servers(self) -> list[MCPServer]:
        """Get all enabled servers."""
        return [s for s in self._servers.values() if s.enabled]

    def list_all(self) -> list[MCPServer]:
        """List all registered servers."""
        return list(self._servers.values())

    def load_from_config(self, servers_config: list[dict[str, Any]]) -> None:
        """Load server configurations from a config dict list."""
        for cfg in servers_config:
            server = MCPServer(
                name=cfg["name"],
                command=cfg.get("command"),
                args=cfg.get("args", []),
                env=cfg.get("env", {}),
                url=cfg.get("url"),
                transport=cfg.get("transport", "stdio"),
                enabled=cfg.get("enabled", True),
                description=cfg.get("description", ""),
            )
            self.register(server)

    def load_defaults(self) -> None:
        """Load default MCP server configurations."""
        for server in DEFAULT_MCP_SERVERS:
            if server.name not in self._servers:
                self.register(MCPServer(
                    name=server.name,
                    command=server.command,
                    args=server.args.copy(),
                    env=server.env.copy(),
                    url=server.url,
                    transport=server.transport,
                    enabled=server.enabled,
                    description=server.description,
                ))
