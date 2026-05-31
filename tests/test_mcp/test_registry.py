"""Tests for MCP Registry."""

import pytest
from sharp.harness.mcp.registry import MCPServer, MCPRegistry, DEFAULT_MCP_SERVERS


class TestMCPServer:
    def test_create_stdio_server(self):
        server = MCPServer(
            name="test",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"],
            transport="stdio",
        )
        assert server.name == "test"
        assert server.transport == "stdio"
        assert server.enabled is True

    def test_create_http_server(self):
        server = MCPServer(
            name="remote",
            url="http://localhost:8000/mcp",
            transport="http",
        )
        assert server.transport == "http"
        assert server.url == "http://localhost:8000/mcp"


class TestMCPRegistry:
    def test_register_and_get(self):
        registry = MCPRegistry()
        server = MCPServer(name="test-server", command="echo")
        registry.register(server)
        assert registry.get("test-server") is server

    def test_get_enabled_servers(self):
        registry = MCPRegistry()
        registry.register(MCPServer(name="enabled", command="echo", enabled=True))
        registry.register(MCPServer(name="disabled", command="echo", enabled=False))
        enabled = registry.get_enabled_servers()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    def test_unregister(self):
        registry = MCPRegistry()
        registry.register(MCPServer(name="test", command="echo"))
        assert registry.unregister("test") is True
        assert registry.get("test") is None
        assert registry.unregister("nonexistent") is False

    def test_load_defaults(self):
        registry = MCPRegistry()
        registry.load_defaults()
        assert len(registry.list_all()) == len(DEFAULT_MCP_SERVERS)
        names = [s.name for s in registry.list_all()]
        assert "filesystem" in names
        assert "github" in names
        assert "postgres" in names

    def test_load_from_config(self):
        registry = MCPRegistry()
        config = [
            {"name": "custom", "command": "python", "args": ["server.py"], "enabled": True},
        ]
        registry.load_from_config(config)
        server = registry.get("custom")
        assert server is not None
        assert server.command == "python"
