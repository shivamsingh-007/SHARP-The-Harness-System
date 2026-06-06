"""Tests for SHARP Dashboard - unit, smoke, and integration."""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.engine import HarnessEngine
from sharp.harness.dashboard.bridge import DashboardBridge
from sharp.harness.dashboard.server import create_app


# ─── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def config():
    return HarnessConfig.default()


@pytest.fixture
def engine(config):
    return HarnessEngine(config)


@pytest.fixture
def bridge(engine):
    return DashboardBridge(engine)


@pytest.fixture
def client(config):
    app = create_app(config)
    return TestClient(app)


# ─── Unit Tests: DashboardBridge ────────────────────────────────────────


class TestDashboardBridgeHealth:
    def test_get_health_returns_running(self, bridge):
        health = bridge.get_health()
        assert health.status == "running"
        assert health.uptime_seconds >= 0
        assert health.environment == "development"

    def test_get_health_connections_count(self, bridge):
        health = bridge.get_health()
        assert health.connections_total >= 1
        assert health.connections_healthy >= 0

    def test_record_run_updates_last_run(self, bridge):
        bridge.record_run()
        health = bridge.get_health()
        assert health.last_run_seconds_ago is not None
        assert health.last_run_seconds_ago < 5

    def test_record_error_stored(self, bridge):
        bridge.record_error("test error")
        safety = bridge.get_safety()
        assert len(safety.recent_errors) == 1
        assert safety.recent_errors[0]["error"] == "test error"


class TestDashboardBridgeMetrics:
    def test_aggregate_initial(self, bridge):
        agg = bridge.get_metrics_aggregate()
        assert agg.total_traces == 0
        assert agg.total_tokens == 0
        assert agg.total_cost == 0.0
        assert agg.success_rate == 100.0
        assert agg.error_rate == 0.0

    def test_aggregate_after_recording(self, engine, bridge):
        engine.metrics.start_trace("t1")
        engine.metrics.end_trace("t1", success=True, latency_ms=100, tokens=50, cost=0.001)
        agg = bridge.get_metrics_aggregate()
        assert agg.total_traces == 1
        assert agg.successful_traces == 1
        assert agg.total_tokens == 50
        assert agg.success_rate == 100.0

    def test_traces_list(self, engine, bridge):
        engine.metrics.start_trace("t1")
        engine.metrics.end_trace("t1", success=True, latency_ms=50, tokens=10, cost=0.001)
        traces = bridge.get_metrics_traces()
        assert len(traces) == 1
        assert traces[0].trace_id == "t1"
        assert traces[0].latency_ms == 50

    def test_timeseries_empty(self, bridge):
        ts = bridge.get_metrics_timeseries()
        assert ts.points == []

    def test_timeseries_with_data(self, engine, bridge):
        for i in range(5):
            tid = f"trace_{i}"
            engine.metrics.start_trace(tid)
            engine.metrics.end_trace(tid, success=True, latency_ms=100 + i * 10, tokens=20, cost=0.001)
        ts = bridge.get_metrics_timeseries(window_minutes=60)
        assert len(ts.points) > 0


class TestDashboardBridgeConnections:
    def test_connections_list(self, bridge):
        conns = bridge.get_connections()
        assert len(conns.connections) >= 3
        ids = [c.id for c in conns.connections]
        assert "llm" in ids
        assert "mcp" in ids
        assert "tools" in ids

    def test_llm_connection_has_metrics(self, bridge):
        conns = bridge.get_connections()
        llm = next(c for c in conns.connections if c.id == "llm")
        assert llm.type == "llm"
        assert len(llm.metrics) == 3
        assert llm.metrics[0].label == "Latency"

    def test_mcp_connection(self, bridge):
        conns = bridge.get_connections()
        mcp = next(c for c in conns.connections if c.id == "mcp")
        assert mcp.type == "mcp"


class TestDashboardBridgeExecution:
    def test_execution_current_idle(self, bridge):
        ex = bridge.get_execution_current()
        assert ex.active is False
        assert ex.done is False
        assert ex.total_steps == 0

    def test_execution_with_loop_state(self, engine, bridge):
        engine.execution_loop._state.iteration = 3
        engine.execution_loop._state.history = [
            {"type": "thought", "content": "I need to search", "iteration": 1, "timestamp": time.time()},
            {"type": "action", "content": "Calling tool", "iteration": 2, "timestamp": time.time()},
        ]
        ex = bridge.get_execution_current()
        assert ex.iteration == 3
        assert len(ex.steps) == 2


class TestDashboardBridgeSafety:
    def test_safety_initial(self, bridge):
        safety = bridge.get_safety()
        assert safety.circuit_breaker.state == "closed"
        assert safety.circuit_breaker.failure_count == 0
        assert safety.budget.session_tokens == 0
        assert safety.budget.session_cost == 0.0

    def test_safety_after_failures(self, engine, bridge):
        engine.circuit_breaker.record_failure()
        engine.circuit_breaker.record_failure()
        safety = bridge.get_safety()
        assert safety.circuit_breaker.failure_count == 2

    def test_safety_after_budget_usage(self, engine, bridge):
        engine.budget_manager.record_tokens(1000)
        engine.budget_manager.record_cost(0.50)
        safety = bridge.get_safety()
        assert safety.budget.session_tokens == 1000
        assert safety.budget.session_cost == 0.50


# ─── Smoke Tests: API Endpoints ─────────────────────────────────────────


class TestAPIHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "uptime_seconds" in data

    def test_health_returns_json(self, client):
        resp = client.get("/api/health")
        assert resp.headers["content-type"] == "application/json"


class TestAPIMetrics:
    def test_metrics_aggregate(self, client):
        resp = client.get("/api/metrics/aggregate")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_traces" in data
        assert "total_tokens" in data
        assert "avg_latency_ms" in data

    def test_metrics_traces(self, client):
        resp = client.get("/api/metrics/traces")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_metrics_timeseries(self, client):
        resp = client.get("/api/metrics/timeseries?window=60")
        assert resp.status_code == 200
        assert "points" in resp.json()


class TestAPIConnections:
    def test_connections_endpoint(self, client):
        resp = client.get("/api/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert "connections" in data
        assert len(data["connections"]) >= 3

    def test_connection_has_required_fields(self, client):
        resp = client.get("/api/connections")
        conn = resp.json()["connections"][0]
        assert "id" in conn
        assert "name" in conn
        assert "status" in conn
        assert "metrics" in conn


class TestAPIExecution:
    def test_execution_current(self, client):
        resp = client.get("/api/execution/current")
        assert resp.status_code == 200
        data = resp.json()
        assert "active" in data
        assert "steps" in data
        assert "strategy" in data


class TestAPISafety:
    def test_safety_endpoint(self, client):
        resp = client.get("/api/safety")
        assert resp.status_code == 200
        data = resp.json()
        assert "circuit_breaker" in data
        assert "budget" in data

    def test_circuit_breaker_fields(self, client):
        resp = client.get("/api/safety")
        cb = resp.json()["circuit_breaker"]
        assert cb["state"] == "closed"
        assert cb["failure_count"] == 0

    def test_budget_fields(self, client):
        resp = client.get("/api/safety")
        budget = resp.json()["budget"]
        assert "session_tokens" in budget
        assert "cost_limit" in budget


class TestAPIConfig:
    def test_config_endpoint(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "execution" in data
        assert "safety" in data


# ─── Integration Test: Full Pipeline ────────────────────────────────────


class TestDashboardIntegration:
    def test_full_pipeline_updates_dashboard(self, client):
        run_resp = client.post("/api/engine/run", json={"request": "What is 2+2?"})
        assert run_resp.status_code == 200

        health = client.get("/api/health").json()
        assert health["last_run_seconds_ago"] is not None

        metrics = client.get("/api/metrics/aggregate").json()
        assert metrics["total_traces"] >= 1

        traces = client.get("/api/metrics/traces").json()
        assert len(traces) >= 1

    def test_multiple_runs_accumulate(self, client):
        client.post("/api/engine/run", json={"request": "test1"})
        client.post("/api/engine/run", json={"request": "test2"})

        metrics = client.get("/api/metrics/aggregate").json()
        assert metrics["total_traces"] >= 2

    def test_safety_reflects_usage(self, client):
        client.post("/api/engine/run", json={"request": "test"})

        safety = client.get("/api/safety").json()
        assert safety["budget"]["total_tokens"] >= 0

    def test_connections_after_run(self, client):
        client.post("/api/engine/run", json={"request": "test"})

        conns = client.get("/api/connections").json()
        assert len(conns["connections"]) >= 3


# ─── Smoke Test: Server Creation ────────────────────────────────────────


class TestServerSmoke:
    def test_app_creates(self):
        app = create_app()
        assert app.title == "SHARP Dashboard"

    def test_app_with_custom_config(self):
        config = HarnessConfig.default()
        app = create_app(config)
        assert app is not None

    def test_all_routes_registered(self):
        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/health" in routes
        assert "/api/metrics/aggregate" in routes
        assert "/api/connections" in routes
        assert "/api/execution/current" in routes
        assert "/api/safety" in routes
        assert "/api/config" in routes
        assert "/ws" in routes
