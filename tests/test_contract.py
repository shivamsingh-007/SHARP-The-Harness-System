"""Contract tests — validate pipeline shapes without mocking internals.

These tests verify:
- Input types → pipeline → output types
- Config variants → engine creation → no crashes
- Error paths → correct exception types
- Tool registration → correct risk levels
"""

from __future__ import annotations

import pytest
from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import HarnessResult, LoopStrategy, RiskLevel


class TestEngineCreation:
    """Contract: engine can be created from various configs."""

    def test_default_config_creates_engine(self):
        engine = HarnessEngine(HarnessConfig.default())
        assert engine is not None

    def test_custom_llm_config_creates_engine(self):
        config = HarnessConfig(
            llm={"provider": "openai", "model": "gpt-4o-mini", "api_key": "test"}
        )
        engine = HarnessEngine(config)
        assert engine is not None

    def test_disabled_validation_creates_engine(self):
        config = HarnessConfig(validation={"enabled": False})
        engine = HarnessEngine(config)
        assert engine is not None


class TestToolRegistration:
    """Contract: built-in tools are registered with correct risk levels."""

    def test_calculate_registered(self):
        engine = HarnessEngine()
        tools = engine.tool_registry.list_tools()
        tool_names = [t.name for t in tools]
        assert "calculate" in tool_names

    def test_read_file_registered(self):
        engine = HarnessEngine()
        tools = engine.tool_registry.list_tools()
        tool_names = [t.name for t in tools]
        assert "read_file" in tool_names

    def test_tools_have_risk_levels(self):
        engine = HarnessEngine()
        tools = engine.tool_registry.list_tools()
        for tool in tools:
            assert hasattr(tool, "risk_level")
            assert isinstance(tool.risk_level, RiskLevel)


class TestPathValidation:
    """Contract: file tools reject paths outside project root."""

    def test_read_file_rejects_traversal(self):
        engine = HarnessEngine()
        result = engine._validate_path("../../etc/passwd")
        assert isinstance(result, str)
        assert "outside project root" in result

    def test_validate_path_accepts_relative(self):
        engine = HarnessEngine()
        result = engine._validate_path("sharp/__init__.py")
        # May or may not exist, but should not be rejected for traversal
        assert not (isinstance(result, str) and "outside project root" in result)


class TestCoTToTNotImplemented:
    """Contract: CoT/ToT raise NotImplementedError."""

    @pytest.mark.asyncio
    async def test_cot_raises(self):
        from unittest.mock import AsyncMock, MagicMock

        config = HarnessConfig(execution={"loop_strategy": LoopStrategy.COT})
        engine = HarnessEngine(config)
        provider = MagicMock()
        provider.complete = AsyncMock()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            await engine.execution_loop.run(provider, "test")

    @pytest.mark.asyncio
    async def test_tot_raises(self):
        from unittest.mock import AsyncMock, MagicMock

        config = HarnessConfig(execution={"loop_strategy": LoopStrategy.TOT})
        engine = HarnessEngine(config)
        provider = MagicMock()
        provider.complete = AsyncMock()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            await engine.execution_loop.run(provider, "test")


class TestDashboardConfig:
    """Contract: DashboardConfig has correct defaults."""

    def test_auth_required_by_default(self):
        from sharp.harness.core.config import DashboardConfig

        dc = DashboardConfig()
        assert dc.auth_required is True
        assert dc.dev_mode is False

    def test_cors_not_wildcard(self):
        from sharp.harness.core.config import DashboardConfig

        dc = DashboardConfig()
        assert "*" not in dc.cors_origins

    def test_rate_limits_positive(self):
        from sharp.harness.core.config import DashboardConfig

        dc = DashboardConfig()
        assert dc.rate_limit_rpm > 0
        assert dc.rate_limit_expensive_rpm > 0
        assert dc.rate_limit_expensive_rpm < dc.rate_limit_rpm


class TestPersistenceKeySanitization:
    """Contract: persistence rejects dangerous keys."""

    def test_rejects_path_traversal(self):
        from sharp.harness.state.persistence import FileBackend

        with pytest.raises(ValueError, match="path traversal"):
            FileBackend._sanitize_key("../../etc/passwd")

    def test_rejects_null_byte(self):
        from sharp.harness.state.persistence import FileBackend

        with pytest.raises(ValueError, match="null byte"):
            FileBackend._sanitize_key("key\x00name")

    def test_rejects_absolute_path(self):
        from sharp.harness.state.persistence import FileBackend

        with pytest.raises(ValueError, match="absolute path"):
            FileBackend._sanitize_key("/etc/passwd")
