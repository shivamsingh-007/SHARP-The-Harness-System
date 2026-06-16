"""Tests for MCP Client - connection, tool invocation, error handling.

Mocks the MCP SDK entirely. No real MCP server needed.
Validates: connection failure, timeout, malformed responses, tool routing,
fallback behavior, disconnect cleanup, telemetry events.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sharp.harness.core.config import MCPConfig, MCPServerConfig
from sharp.harness.mcp.client import MCPClient, _schema_to_dict


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_mcp_config(*servers: MCPServerConfig) -> MCPConfig:
    config = MCPConfig()
    config.servers = list(servers)
    return config


def _make_stdio_config(name: str = "test-server") -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport="stdio",
        command="echo",
        args=["hello"],
    )


def _make_http_config(name: str = "test-server", url: str = "http://localhost:8000/mcp") -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport="http",
        url=url,
    )


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    session.list_resources = AsyncMock(return_value=MagicMock(resources=[]))
    session.list_resource_templates = AsyncMock(return_value=MagicMock(resourceTemplates=[]))
    session.list_prompts = AsyncMock(return_value=MagicMock(prompts=[]))
    session.call_tool = AsyncMock()
    session.read_resource = AsyncMock()
    session.get_prompt = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _mock_tool(name: str = "read_file", description: str = "Read a file", input_schema: dict | None = None) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = input_schema or {"type": "object", "properties": {}}
    return tool


def _mock_resource(name: str = "config", uri: str = "file:///config.json", description: str = "Config file") -> MagicMock:
    resource = MagicMock()
    resource.name = name
    resource.uri = uri
    resource.description = description
    resource.mimeType = "application/json"
    return resource


def _mock_resource_template(uri_template: str = "file:///{path}", description: str = "File template") -> MagicMock:
    template = MagicMock()
    template.uriTemplate = uri_template
    template.description = description
    return template


def _mock_prompt(name: str = "summarize", description: str = "Summarize text") -> MagicMock:
    prompt = MagicMock()
    prompt.name = name
    prompt.description = description
    prompt.arguments = []
    return prompt


def _mock_tool_result(output: str = "result", is_error: bool = False) -> MagicMock:
    result = MagicMock()
    result.isError = is_error
    content = MagicMock()
    content.text = output
    result.content = [content]
    return result


def _mock_resource_result(text: str = "resource content", uri: str = "file:///config.json") -> MagicMock:
    result = MagicMock()
    content = MagicMock()
    content.text = text
    content.uri = uri
    content.mimeType = "application/json"
    result.contents = [content]
    return result


def _mock_prompt_result(content_text: str = "prompt text") -> MagicMock:
    result = MagicMock()
    msg = MagicMock()
    msg.role = "user"
    msg.content = MagicMock()
    msg.content.text = content_text
    result.messages = [msg]
    return result


# ── Connection Tests ─────────────────────────────────────────────────────


class TestConnectStdio:
    @pytest.mark.asyncio
    async def test_connect_stdio_success(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        mock_session = _mock_session()

        with patch("sharp.harness.mcp.client.MCPClient._discover_capabilities", new_callable=AsyncMock):
            with patch("mcp.ClientSession", return_value=mock_session):
                with patch("mcp.client.stdio.stdio_client") as mock_stdio:
                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_stdio.return_value = mock_ctx

                    await client.connect_stdio("test-server", "echo", ["hello"])

                    assert "test-server" in client.connected_servers
                    assert mock_session.initialize.called

    @pytest.mark.asyncio
    async def test_connect_stdio_already_connected(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        client._connected.add("test-server")

        await client.connect_stdio("test-server", "echo", ["hello"])
        assert "test-server" in client.connected_servers

    @pytest.mark.asyncio
    async def test_connect_stdio_sdk_not_installed(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)

        with patch("builtins.__import__", side_effect=ImportError("No module named 'mcp'")):
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                await client.connect_stdio("test-server", "echo", ["hello"])

    @pytest.mark.asyncio
    async def test_connect_stdio_session_fails(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)

        with patch("mcp.ClientSession") as MockSession:
            mock_session = _mock_session()
            mock_session.initialize.side_effect = RuntimeError("Connection refused")
            MockSession.return_value = mock_session

            with patch("mcp.client.stdio.stdio_client") as mock_stdio:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                mock_stdio.return_value = mock_ctx

                with pytest.raises(RuntimeError, match="Connection refused"):
                    await client.connect_stdio("test-server", "echo", ["hello"])

                assert "test-server" not in client.connected_servers
                events = client._telemetry.get_events("mcp.connection_failed")
                assert len(events) == 1
                assert events[0].data["server"] == "test-server"


class TestConnectHTTP:
    @pytest.mark.asyncio
    async def test_connect_http_success(self):
        config = _make_mcp_config(_make_http_config())
        client = MCPClient(config)
        mock_session = _mock_session()

        with patch("sharp.harness.mcp.client.MCPClient._discover_capabilities", new_callable=AsyncMock):
            with patch("mcp.ClientSession", return_value=mock_session):
                with patch("mcp.client.streamable_http.streamable_http_client") as mock_http:
                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), AsyncMock()))
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_http.return_value = mock_ctx

                    await client.connect_http("test-server", "http://localhost:8000/mcp")

                    assert "test-server" in client.connected_servers

    @pytest.mark.asyncio
    async def test_connect_http_bad_url(self):
        config = _make_mcp_config(_make_http_config(url="http://invalid:99999/mcp"))
        client = MCPClient(config)

        with patch("mcp.ClientSession") as MockSession:
            mock_session = _mock_session()
            mock_session.initialize.side_effect = ConnectionRefusedError("Connection refused")
            MockSession.return_value = mock_session

            with patch("mcp.client.streamable_http.streamable_http_client") as mock_http:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), AsyncMock()))
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                mock_http.return_value = mock_ctx

                with pytest.raises(ConnectionRefusedError):
                    await client.connect_http("test-server", "http://invalid:99999/mcp")

                assert "test-server" not in client.connected_servers


class TestConnectFromConfig:
    @pytest.mark.asyncio
    async def test_connect_from_config_stdio(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)

        with patch.object(client, "connect_stdio", new_callable=AsyncMock) as mock_connect:
            await client.connect_from_config(_make_stdio_config())
            mock_connect.assert_called_once_with("test-server", "echo", ["hello"], {})

    @pytest.mark.asyncio
    async def test_connect_from_config_http(self):
        config = _make_mcp_config(_make_http_config())
        client = MCPClient(config)

        with patch.object(client, "connect_http", new_callable=AsyncMock) as mock_connect:
            await client.connect_from_config(_make_http_config())
            mock_connect.assert_called_once_with("test-server", "http://localhost:8000/mcp")

    @pytest.mark.asyncio
    async def test_connect_from_config_stdio_missing_command(self):
        bad_config = MCPServerConfig(name="bad", transport="stdio")
        client = MCPClient(MCPConfig())

        with pytest.raises(ValueError, match="requires 'command'"):
            await client.connect_from_config(bad_config)

    @pytest.mark.asyncio
    async def test_connect_from_config_http_missing_url(self):
        bad_config = MCPServerConfig(name="bad", transport="http")
        client = MCPClient(MCPConfig())

        with pytest.raises(ValueError, match="requires 'url'"):
            await client.connect_from_config(bad_config)


# ── Tool Call Tests ──────────────────────────────────────────────────────


class TestCallTool:
    def _setup_client_with_tool(self, tool_name: str = "read_file", server: str = "test-server") -> MCPClient:
        config = _make_mcp_config(_make_stdio_config(server))
        client = MCPClient(config)
        client._connected.add(server)
        client._tool_server_map[tool_name] = server
        client._sessions[server] = _mock_session()
        return client

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        client = self._setup_client_with_tool()
        client._sessions["test-server"].call_tool.return_value = _mock_tool_result("file contents")

        result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})

        assert result["success"] is True
        assert result["output"] == "file contents"
        assert result["tool_name"] == "read_file"
        assert result["server"] == "test-server"

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        client = self._setup_client_with_tool()

        result = await client.call_tool("nonexistent_tool", {})

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_server_disconnected(self):
        client = self._setup_client_with_tool()
        client._sessions.clear()

        result = await client.call_tool("read_file", {})

        assert "error" in result
        assert "not connected" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_is_error_flag(self):
        client = self._setup_client_with_tool()
        client._sessions["test-server"].call_tool.return_value = _mock_tool_result("error occurred", is_error=True)

        result = await client.call_tool("read_file", {})

        assert result["is_error"] is True
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_call_tool_empty_result(self):
        client = self._setup_client_with_tool()
        empty_result = MagicMock()
        empty_result.isError = False
        empty_result.content = []
        client._sessions["test-server"].call_tool.return_value = empty_result

        result = await client.call_tool("read_file", {})

        assert result["output"] == ""

    @pytest.mark.asyncio
    async def test_call_tool_binary_content(self):
        """Binary content (has data/mimeType, no text) → formatted output."""
        client = self._setup_client_with_tool(tool_name="get_image")

        # Create a content object that has data+mimeType but NOT text
        class BinaryContent:
            def __init__(self):
                self.data = "base64data"
                self.mimeType = "image/png"

        result_mock = MagicMock()
        result_mock.isError = False
        result_mock.content = [BinaryContent()]
        client._sessions["test-server"].call_tool.return_value = result_mock

        result = await client.call_tool("get_image", {})

        assert result["success"] is True
        assert "image/png" in result["output"]
        assert "base64data" in result["output"]

    @pytest.mark.asyncio
    async def test_call_tool_session_exception(self):
        client = self._setup_client_with_tool()
        client._sessions["test-server"].call_tool.side_effect = RuntimeError("Timeout")

        result = await client.call_tool("read_file", {})

        assert "error" in result
        assert "Timeout" in result["error"]
        assert result["tool_name"] == "read_file"

    @pytest.mark.asyncio
    async def test_call_tool_telemetry_recorded(self):
        client = self._setup_client_with_tool()
        client._sessions["test-server"].call_tool.return_value = _mock_tool_result("ok")

        await client.call_tool("read_file", {"path": "/tmp/test.txt"})

        events = client._telemetry.get_events("mcp.tool_call")
        assert len(events) == 1
        assert events[0].data["tool"] == "read_file"
        assert events[0].data["server"] == "test-server"


# ── Resource Tests ───────────────────────────────────────────────────────


class TestReadResource:
    def _setup_client_with_resource(self, uri: str = "file:///config.json", server: str = "test-server") -> MCPClient:
        config = _make_mcp_config(_make_stdio_config(server))
        client = MCPClient(config)
        client._connected.add(server)
        client._resource_server_map[uri] = server
        client._sessions[server] = _mock_session()
        return client

    @pytest.mark.asyncio
    async def test_read_resource_success(self):
        client = self._setup_client_with_resource()
        client._sessions["test-server"].read_resource.return_value = _mock_resource_result("config data")

        result = await client.read_resource("file:///config.json")

        assert result["success"] is True
        assert len(result["contents"]) == 1
        assert result["contents"][0]["text"] == "config data"

    @pytest.mark.asyncio
    async def test_read_resource_not_found(self):
        client = self._setup_client_with_resource()

        result = await client.read_resource("file:///nonexistent.json")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_read_resource_session_exception(self):
        client = self._setup_client_with_resource()
        client._sessions["test-server"].read_resource.side_effect = RuntimeError("Permission denied")

        result = await client.read_resource("file:///config.json")

        assert "error" in result
        assert "Permission denied" in result["error"]


# ── Prompt Tests ─────────────────────────────────────────────────────────


class TestGetPrompt:
    def _setup_client_with_prompt(self, name: str = "summarize", server: str = "test-server") -> MCPClient:
        config = _make_mcp_config(_make_stdio_config(server))
        client = MCPClient(config)
        client._connected.add(server)
        client._prompt_server_map[name] = server
        client._sessions[server] = _mock_session()
        return client

    @pytest.mark.asyncio
    async def test_get_prompt_success(self):
        client = self._setup_client_with_prompt()
        client._sessions["test-server"].get_prompt.return_value = _mock_prompt_result("Summarize this text")

        result = await client.get_prompt("summarize", {"text": "hello"})

        assert result["success"] is True
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Summarize this text"

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(self):
        client = self._setup_client_with_prompt()

        result = await client.get_prompt("nonexistent", {})

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_prompt_session_exception(self):
        client = self._setup_client_with_prompt()
        client._sessions["test-server"].get_prompt.side_effect = RuntimeError("Server error")

        result = await client.get_prompt("summarize", {})

        assert "error" in result


# ── Disconnect Tests ─────────────────────────────────────────────────────


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_cleans_tool_mappings(self):
        config = _make_mcp_config(_make_stdio_config("server-a"))
        client = MCPClient(config)
        client._connected.add("server-a")
        client._tool_server_map["tool_a"] = "server-a"
        client._tool_server_map["tool_b"] = "server-b"
        client._sessions["server-a"] = _mock_session()

        await client.disconnect("server-a")

        assert "tool_a" not in client._tool_server_map
        assert "tool_b" in client._tool_server_map

    @pytest.mark.asyncio
    async def test_disconnect_cleans_resource_mappings(self):
        config = _make_mcp_config(_make_stdio_config("server-a"))
        client = MCPClient(config)
        client._connected.add("server-a")
        client._resource_server_map["uri_a"] = "server-a"
        client._sessions["server-a"] = _mock_session()

        await client.disconnect("server-a")

        assert "uri_a" not in client._resource_server_map

    @pytest.mark.asyncio
    async def test_disconnect_cleans_prompt_mappings(self):
        config = _make_mcp_config(_make_stdio_config("server-a"))
        client = MCPClient(config)
        client._connected.add("server-a")
        client._prompt_server_map["prompt_a"] = "server-a"
        client._sessions["server-a"] = _mock_session()

        await client.disconnect("server-a")

        assert "prompt_a" not in client._prompt_server_map

    @pytest.mark.asyncio
    async def test_disconnect_removes_discovered_items(self):
        config = _make_mcp_config(_make_stdio_config("server-a"))
        client = MCPClient(config)
        client._connected.add("server-a")
        client._discovered_tools["tool_a"] = {"name": "tool_a", "server": "server-a"}
        client._discovered_tools["tool_b"] = {"name": "tool_b", "server": "server-b"}
        client._sessions["server-a"] = _mock_session()

        await client.disconnect("server-a")

        assert "tool_a" not in client._discovered_tools
        assert "tool_b" in client._discovered_tools

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        config = _make_mcp_config(_make_stdio_config("server-a"))
        client = MCPClient(config)

        await client.disconnect("server-a")

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        config = _make_mcp_config(_make_stdio_config("s1"), _make_stdio_config("s2"))
        client = MCPClient(config)
        client._connected.add("s1")
        client._connected.add("s2")
        client._sessions["s1"] = _mock_session()
        client._sessions["s2"] = _mock_session()

        await client.disconnect_all()

        assert len(client.connected_servers) == 0

    @pytest.mark.asyncio
    async def test_disconnect_telemetry_recorded(self):
        config = _make_mcp_config(_make_stdio_config("server-a"))
        client = MCPClient(config)
        client._connected.add("server-a")
        client._sessions["server-a"] = _mock_session()

        await client.disconnect("server-a")

        events = client._telemetry.get_events("mcp.disconnected")
        assert len(events) == 1
        assert events[0].data["server"] == "server-a"


# ── Discovery Tests ──────────────────────────────────────────────────────


class TestDiscoverCapabilities:
    @pytest.mark.asyncio
    async def test_discover_tools(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        mock_session = _mock_session()
        mock_session.list_tools.return_value = MagicMock(
            tools=[_mock_tool("read_file", "Read a file"), _mock_tool("write_file", "Write a file")]
        )

        client._sessions["test-server"] = mock_session
        client._connected.add("test-server")

        await client._discover_capabilities("test-server")

        assert "read_file" in client.discovered_tools
        assert "write_file" in client.discovered_tools
        assert client._tool_server_map["read_file"] == "test-server"

    @pytest.mark.asyncio
    async def test_discover_resources(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        mock_session = _mock_session()
        mock_session.list_resources.return_value = MagicMock(
            resources=[_mock_resource("config", "file:///config.json")]
        )

        client._sessions["test-server"] = mock_session
        client._connected.add("test-server")

        await client._discover_capabilities("test-server")

        assert "file:///config.json" in client.discovered_resources

    @pytest.mark.asyncio
    async def test_discover_prompts(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        mock_session = _mock_session()
        mock_session.list_prompts.return_value = MagicMock(
            prompts=[_mock_prompt("summarize", "Summarize text")]
        )

        client._sessions["test-server"] = mock_session
        client._connected.add("test-server")

        await client._discover_capabilities("test-server")

        assert "summarize" in client.discovered_prompts
        assert client._prompt_server_map["summarize"] == "test-server"

    @pytest.mark.asyncio
    async def test_discover_partial_failure(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        mock_session = _mock_session()
        mock_session.list_tools.side_effect = RuntimeError("Tools unavailable")
        mock_session.list_resources.return_value = MagicMock(
            resources=[_mock_resource("config", "file:///config.json")]
        )

        client._sessions["test-server"] = mock_session
        client._connected.add("test-server")

        await client._discover_capabilities("test-server")

        assert len(client.discovered_tools) == 0
        assert "file:///config.json" in client.discovered_resources

    @pytest.mark.asyncio
    async def test_discover_resource_templates(self):
        config = _make_mcp_config(_make_stdio_config())
        client = MCPClient(config)
        mock_session = _mock_session()
        mock_session.list_resource_templates.return_value = MagicMock(
            resourceTemplates=[_mock_resource_template("file:///{path}")]
        )

        client._sessions["test-server"] = mock_session
        client._connected.add("test-server")

        await client._discover_capabilities("test-server")

        assert "file:///{path}" in client.discovered_resources


# ── Schema Conversion Tests ──────────────────────────────────────────────


class TestSchemaConversion:
    def test_dict_passthrough(self):
        schema = {"type": "object", "properties": {"path": {"type": "string"}}}
        assert _schema_to_dict(schema) == schema

    def test_pydantic_model(self):
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"type": "object"}
        result = _schema_to_dict(mock_model)
        assert result == {"type": "object"}

    def test_old_pydantic(self):
        mock_model = MagicMock()
        del mock_model.model_dump
        mock_model.dict.return_value = {"type": "object"}
        result = _schema_to_dict(mock_model)
        assert result == {"type": "object"}

    def test_json_serializable(self):
        schema = {"type": "object", "default": None}
        result = _schema_to_dict(schema)
        assert result["type"] == "object"

    def test_unconvertible_returns_something(self):
        class Unconvertible:
            def __repr__(self):
                return "<unconvertible>"

        result = _schema_to_dict(Unconvertible())
        # json.dumps(default=str) serializes to a string, json.loads parses it
        # The result is whatever json round-trips to — just verify no crash
        assert result is not None


# ── Utility Tests ────────────────────────────────────────────────────────


class TestMCPClientProperties:
    def test_connected_servers_empty(self):
        config = _make_mcp_config()
        client = MCPClient(config)
        assert client.connected_servers == []

    def test_discovered_tools_empty(self):
        config = _make_mcp_config()
        client = MCPClient(config)
        assert client.discovered_tools == {}

    def test_discovered_resources_empty(self):
        config = _make_mcp_config()
        client = MCPClient(config)
        assert client.discovered_resources == {}

    def test_discovered_prompts_empty(self):
        config = _make_mcp_config()
        client = MCPClient(config)
        assert client.discovered_prompts == {}

    def test_get_tools_for_server(self):
        config = _make_mcp_config()
        client = MCPClient(config)
        client._discovered_tools = {
            "tool_a": {"name": "tool_a", "server": "s1"},
            "tool_b": {"name": "tool_b", "server": "s2"},
        }
        tools = client.get_tools_for_server("s1")
        assert len(tools) == 1
        assert tools[0]["name"] == "tool_a"

    def test_get_all_tools_flat(self):
        config = _make_mcp_config()
        client = MCPClient(config)
        client._discovered_tools = {
            "tool_a": {"name": "tool_a", "server": "s1"},
            "tool_b": {"name": "tool_b", "server": "s2"},
        }
        tools = client.get_all_tools_flat()
        assert len(tools) == 2
