"""Tests for safety layer."""

import pytest
import time
from sharp.harness.safety.circuit_breaker import CircuitBreaker
from sharp.harness.safety.budget import BudgetManager
from sharp.harness.safety.permissions import PermissionManager
from sharp.harness.core.config import SafetyConfig
from sharp.harness.core.errors import CircuitBreakerOpenError, BudgetExceededError
from sharp.harness.core.types import RiskLevel


class TestCircuitBreaker:
    def test_initial_state(self):
        config = SafetyConfig(failure_threshold=3)
        cb = CircuitBreaker(config)
        assert cb.state == "closed"

    def test_opens_after_threshold(self):
        config = SafetyConfig(failure_threshold=3)
        cb = CircuitBreaker(config)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"

    def test_check_raises_when_open(self):
        config = SafetyConfig(failure_threshold=1)
        cb = CircuitBreaker(config)
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            cb.check()

    def test_recovery(self):
        config = SafetyConfig(failure_threshold=1, recovery_seconds=0.1)
        cb = CircuitBreaker(config)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == "half_open"
        cb.check()  # Should not raise
        cb.record_success()
        assert cb.state == "closed"


class TestBudgetManager:
    def test_within_budget(self):
        config = SafetyConfig(max_cost_usd=10.0, max_tokens=100000)
        bm = BudgetManager(config)
        bm.record_cost(5.0)
        bm.record_tokens(50000)
        bm.check()  # Should not raise

    def test_cost_exceeded(self):
        config = SafetyConfig(max_cost_usd=5.0)
        bm = BudgetManager(config)
        bm.record_cost(6.0)
        with pytest.raises(BudgetExceededError):
            bm.check()

    def test_token_exceeded(self):
        config = SafetyConfig(max_tokens=1000)
        bm = BudgetManager(config)
        bm.record_tokens(1500)
        with pytest.raises(BudgetExceededError):
            bm.check()


class TestPermissionManager:
    def test_allowed_tool(self):
        pm = PermissionManager()
        result = pm.check_permission("read_file", RiskLevel.READ)
        assert result["allowed"]

    def test_blocked_tool(self):
        pm = PermissionManager(blocked_tools=["dangerous_tool"])
        result = pm.check_permission("dangerous_tool", RiskLevel.READ)
        assert not result["allowed"]

    def test_approval_required(self):
        pm = PermissionManager(require_approval_for=[RiskLevel.EXECUTE])
        result = pm.check_permission(
            "run_command", RiskLevel.EXECUTE, requires_approval=True
        )
        assert not result["allowed"]

    def test_approval_granted(self):
        pm = PermissionManager(require_approval_for=[RiskLevel.EXECUTE])
        pm.approve_tool("run_command")
        result = pm.check_permission(
            "run_command", RiskLevel.EXECUTE, requires_approval=True
        )
        assert result["allowed"]
