"""Tests for core engine."""

import pytest
from sharp.harness.core.engine import HarnessEngine
from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.types import RiskLevel


class TestHarnessEngine:
    def test_init_default(self):
        engine = HarnessEngine()
        assert engine.config is not None
        assert engine._trace_id is not None

    def test_init_custom_config(self):
        config = HarnessConfig()
        config.llm.model = "gpt-4o-mini"
        engine = HarnessEngine(config)
        assert engine.config.llm.model == "gpt-4o-mini"

    def test_add_memory(self):
        engine = HarnessEngine()
        engine.add_memory("key", "value")
        assert engine._memory["key"] == "value"

    def test_tool_registration(self):
        engine = HarnessEngine()

        @engine.tool(risk_level=RiskLevel.READ)
        async def test_tool(x: str) -> str:
            """Test tool."""
            return x

        assert len(engine._tools) == 1
        assert engine._tools[0].name == "test_tool"
