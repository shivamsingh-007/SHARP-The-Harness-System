"""Tests for MCP Client."""

import pytest
from sharp.harness.mcp.client import MCPClient
from sharp.harness.core.config import MCPConfig


class TestMCPClientInit:
    def test_init_default(self):
        config = MCPConfig()
        client = MCPClient(config)
        assert client.connected_servers == []
        assert client.discovered_tools == {}
        assert client.discovered_resources == {}
        assert client.discovered_prompts == {}

    def test_init_with_servers(self):
        config = MCPConfig(
            servers=[
                {"name": "test", "command": "echo", "enabled": True},
            ]
        )
        client = MCPClient(config)
        # Servers are in config, not auto-registered in client.registry
        # Client.registry is used for runtime registration
        assert len(config.servers) == 1
        assert client.connected_servers == []


class TestMCPClientConnection:
    def test_connect_stdio_not_installed(self):
        """Test that connect_stdio raises ImportError if mcp not installed."""
        config = MCPConfig()
        client = MCPClient(config)

        # This test only works if mcp is not installed
        # In production, mcp should be installed
        try:
            import mcp
            pytest.skip("MCP SDK is installed, cannot test import error")
        except ImportError:
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                import asyncio
                asyncio.run(client.connect_stdio("test", "echo"))


class TestMCPClientToolCalls:
    def test_call_tool_not_connected(self):
        config = MCPConfig()
        client = MCPClient(config)
        import asyncio
        result = asyncio.run(client.call_tool("nonexistent", {}))
        assert "error" in result
        assert "not found" in result["error"]
