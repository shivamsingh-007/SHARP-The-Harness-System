"""Tests for MCP Bridge."""

import pytest
from sharp.harness.mcp.bridge import MCPToToolBridge, _READ_KEYWORDS, _WRITE_KEYWORDS
from sharp.harness.mcp.client import MCPClient
from sharp.harness.core.types import RiskLevel
from sharp.harness.core.config import MCPConfig


class TestRiskAssessment:
    def setup_method(self):
        self.bridge = MCPToToolBridge(MCPClient(MCPConfig()))

    def test_read_tools(self):
        for keyword in ["read_file", "get_data", "list_items", "search_docs"]:
            risk = self.bridge._assess_risk(keyword)
            assert risk == RiskLevel.READ, f"'{keyword}' should be READ"

    def test_write_tools(self):
        for keyword in ["write_file", "create_item", "update_record", "save_data"]:
            risk = self.bridge._assess_risk(keyword)
            assert risk == RiskLevel.WRITE, f"'{keyword}' should be WRITE"

    def test_execute_tools(self):
        for keyword in ["run_command", "execute_script", "call_api"]:
            risk = self.bridge._assess_risk(keyword)
            assert risk == RiskLevel.EXECUTE, f"'{keyword}' should be EXECUTE"

    def test_critical_tools(self):
        for keyword in ["delete_file", "drop_table", "remove_item", "destroy_all"]:
            risk = self.bridge._assess_risk(keyword)
            assert risk == RiskLevel.CRITICAL, f"'{keyword}' should be CRITICAL"

    def test_unknown_defaults_to_read(self):
        risk = self.bridge._assess_risk("some_random_tool")
        assert risk == RiskLevel.READ


class TestToolDefinitionConversion:
    def setup_method(self):
        self.bridge = MCPToToolBridge(MCPClient(MCPConfig()))

    def test_to_tool_definition(self):
        mcp_tool = {
            "name": "read_file",
            "description": "Read a file from disk",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            "server": "filesystem",
        }
        tool_def = self.bridge.to_tool_definition(mcp_tool)
        assert tool_def.name == "read_file"
        assert tool_def.description == "Read a file from disk"
        assert tool_def.risk_level == RiskLevel.READ
        assert "path" in tool_def.parameters.get("properties", {})

    def test_to_tool_definition_with_schema(self):
        mcp_tool = {
            "name": "execute_sql",
            "description": "Execute SQL query",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "server": "postgres",
        }
        tool_def = self.bridge.to_tool_definition(mcp_tool)
        assert tool_def.risk_level == RiskLevel.EXECUTE
        assert tool_def.requires_approval is True
