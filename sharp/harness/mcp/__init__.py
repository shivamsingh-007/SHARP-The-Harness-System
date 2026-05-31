"""MCP (Model Context Protocol) module - connects harness to MCP servers."""

from sharp.harness.mcp.client import MCPClient
from sharp.harness.mcp.registry import MCPServer, MCPRegistry, DEFAULT_MCP_SERVERS
from sharp.harness.mcp.bridge import MCPToToolBridge

__all__ = [
    "MCPClient",
    "MCPServer",
    "MCPRegistry",
    "DEFAULT_MCP_SERVERS",
    "MCPToToolBridge",
]
