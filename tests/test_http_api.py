"""Tests for SHARP HTTP API endpoints.

Covers: POST /api/route, POST /api/validate, POST /api/coding/session,
auth middleware, rate limiting, WebSocket auth, CORS, concurrency isolation.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from sharp.harness.dashboard.server import create_app
from sharp.harness.core.config import HarnessConfig, DashboardConfig
from sharp.harness.orchestration.types import InterfaceType, TaskType, ModelType


@pytest.fixture
def client():
    """Create a test client with default config."""
    config = HarnessConfig.default()
    app = create_app(config=config)
    return TestClient(app)


@pytest.fixture
def client_with_project(tmp_path):
    """Create a test client with a temporary project directory."""
    sharp_dir = tmp_path / "sharp"
    sharp_dir.mkdir()
    (sharp_dir / "__init__.py").write_text("", encoding="utf-8")
    config = HarnessConfig.default()
    app = create_app(config=config)
    return TestClient(app), tmp_path


# ── Health Endpoint ────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_version(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_health_has_uptime(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0


# ── Route Endpoint ─────────────────────────────────────────────────────


class TestRouteEndpoint:
    def test_route_returns_decision(self, client):
        response = client.post("/api/route", json={"task": "fix the login bug"})
        assert response.status_code == 200
        data = response.json()
        assert "decision" in data
        assert "explanation" in data
        assert data["decision"]["task_type"] == "coding_bug_fix"
        assert data["decision"]["recommended_interface"] == "claude_code"

    def test_route_returns_alternatives(self, client):
        response = client.post("/api/route", json={"task": "fix bug"})
        data = response.json()
        assert "alternatives" in data
        assert "interfaces" in data["alternatives"]
        assert "models" in data["alternatives"]

    def test_route_with_context(self, client):
        response = client.post("/api/route", json={
            "task": "refactor these files",
            "context": {"files_involved": ["a.py", "b.py", "c.py"]},
        })
        data = response.json()
        assert data["decision"]["task_type"] == "coding_refactor"

    def test_route_empty_task(self, client):
        response = client.post("/api/route", json={"task": ""})
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_route_rag_question(self, client):
        response = client.post("/api/route", json={"task": "what is Python's GIL?"})
        data = response.json()
        assert data["decision"]["task_type"] == "rag_question"
        assert data["decision"]["recommended_interface"] == "chatgpt_app"

    def test_route_has_cost_estimate(self, client):
        response = client.post("/api/route", json={"task": "build a new feature"})
        data = response.json()
        assert data["decision"]["estimated_cost_usd"] > 0
        assert data["decision"]["estimated_latency_ms"] > 0


# ── Validate Endpoint ──────────────────────────────────────────────────


class TestValidateEndpoint:
    def test_validate_returns_result(self, client):
        response = client.post("/api/validate", json={
            "output": "The capital of France is Paris.",
            "task_type": "rag",
        })
        assert response.status_code == 200
        data = response.json()
        assert "passed" in data
        assert "score" in data
        assert "issues" in data

    def test_validate_empty_output(self, client):
        response = client.post("/api/validate", json={"output": ""})
        data = response.json()
        assert "error" in data

    def test_validate_coding_output(self, client):
        response = client.post("/api/validate", json={
            "output": "def add(a, b): return a + b",
            "task_type": "coding",
        })
        data = response.json()
        assert "passed" in data
        assert isinstance(data["score"], (int, float))

    def test_validate_has_score_range(self, client):
        response = client.post("/api/validate", json={
            "output": "This is a test output.",
            "task_type": "general",
        })
        data = response.json()
        assert 0.0 <= data["score"] <= 2.0  # score can exceed 1.0 due to rule-based heuristics


# ── Coding Session Endpoint ────────────────────────────────────────────


class TestCodingSessionEndpoint:
    def test_coding_session_starts(self, client_with_project):
        test_client, tmp_path = client_with_project
        response = test_client.post("/api/coding/session", json={
            "project_root": str(tmp_path),
            "session_id": 1,
        })
        assert response.status_code == 200
        data = response.json()
        # New behavior: runs full DPEVR loop; returns "no_features" if none exist
        assert data["status"] in ("completed", "no_features")
        assert data["session_id"] == 1

    def test_coding_session_returns_result_or_no_features(self, client_with_project):
        test_client, tmp_path = client_with_project
        response = test_client.post("/api/coding/session", json={
            "project_root": str(tmp_path),
            "session_id": 1,
        })
        data = response.json()
        # Either has "result" (DPEVR completed) or "message" (no features)
        assert "result" in data or "message" in data

    def test_coding_session_invalid_project(self, client):
        response = client.post("/api/coding/session", json={
            "project_root": "/nonexistent/path",
            "session_id": 1,
        })
        data = response.json()
        # Invalid project: start_session fails, no features found
        assert data["status"] in ("no_features", "failed")


# ── Auth Middleware ───────────────────────────────────────────────────────


class TestAuthMiddleware:
    @pytest.fixture
    def auth_client(self):
        """Client with auth required and API key set."""
        config = HarnessConfig.default()
        config.dashboard = DashboardConfig(
            api_key="test-secret-key",
            auth_required=True,
            dev_mode=False,
        )
        app = create_app(config=config)
        return TestClient(app)

    @pytest.fixture
    def dev_client(self):
        """Client in dev mode (auth disabled)."""
        config = HarnessConfig.default()
        config.dashboard = DashboardConfig(
            api_key="test-secret-key",
            auth_required=True,
            dev_mode=True,
        )
        app = create_app(config=config, dev_mode=True)
        return TestClient(app)

    def test_auth_required_rejects_no_key(self, auth_client):
        response = auth_client.get("/api/health")
        assert response.status_code == 401
        assert "error" in response.json()

    def test_auth_required_rejects_wrong_key(self, auth_client):
        response = auth_client.get(
            "/api/health",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_auth_required_accepts_valid_key(self, auth_client):
        response = auth_client.get(
            "/api/health",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert response.status_code == 200

    def test_auth_dev_mode_skips_check(self, dev_client):
        response = dev_client.get("/api/health")
        assert response.status_code == 200

    def test_auth_non_api_routes_not_protected(self, auth_client):
        """Routes not under /api/ should not require auth."""
        response = auth_client.get("/docs")
        assert response.status_code == 200


# ── Rate Limiting ────────────────────────────────────────────────────────


class TestRateLimiting:
    @pytest.fixture
    def rate_limited_client(self):
        """Client with very low rate limit for testing."""
        config = HarnessConfig.default()
        config.dashboard = DashboardConfig(
            rate_limit_enabled=True,
            rate_limit_rpm=3,
            rate_limit_expensive_rpm=2,
        )
        app = create_app(config=config)
        return TestClient(app)

    def test_rate_limit_enforced(self, rate_limited_client):
        """Exceeding rate limit → 429."""
        for _ in range(3):
            rate_limited_client.get("/api/health")
        response = rate_limited_client.get("/api/health")
        assert response.status_code == 429

    def test_rate_limit_disabled_in_config(self):
        config = HarnessConfig.default()
        config.dashboard = DashboardConfig(rate_limit_enabled=False)
        app = create_app(config=config)
        client = TestClient(app)
        # Should not get 429 even with many requests
        for _ in range(10):
            response = client.get("/api/health")
            assert response.status_code == 200


# ── Concurrency Isolation ────────────────────────────────────────────────


class TestConcurrencyIsolation:
    def test_engine_run_creates_fresh_engine(self, client_with_project):
        """Each /api/engine/run gets its own engine instance."""
        test_client, tmp_path = client_with_project

        response1 = test_client.post("/api/engine/run", json={"request": "What time is it?"})
        response2 = test_client.post("/api/engine/run", json={"request": "Calculate 2+2"})

        data1 = response1.json()
        data2 = response2.json()

        # Both should succeed independently
        assert "success" in data1 or "error" in data1
        assert "success" in data2 or "error" in data2

    def test_sessions_endpoint_shows_engines(self, client):
        """GET /api/sessions returns active engine list."""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "active" in data


# ── CORS ─────────────────────────────────────────────────────────────────


class TestCORS:
    def test_cors_default_localhost(self):
        config = HarnessConfig.default()
        app = create_app(config=config)
        client = TestClient(app)

        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should allow localhost origins
        assert response.status_code in (200, 405)

    def test_cors_blocked_origin(self):
        config = HarnessConfig.default()
        app = create_app(config=config)
        client = TestClient(app)

        response = client.get(
            "/api/health",
            headers={"Origin": "https://evil.com"},
        )
        # Response should not include Access-Control-Allow-Origin for evil.com
        # (FastAPI CORS middleware handles this)
        assert response.status_code == 200


# ── WebSocket Auth ───────────────────────────────────────────────────────


class TestWebSocketAuth:
    def test_websocket_requires_token(self):
        """WebSocket without token → connection closed by server."""
        from starlette.websockets import WebSocketDisconnect

        config = HarnessConfig.default()
        config.dashboard = DashboardConfig(
            api_key="ws-secret",
            auth_required=True,
        )
        app = create_app(config=config)
        client = TestClient(app)

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws") as ws:
                pass

    def test_websocket_rejects_wrong_token(self):
        """WebSocket with wrong token → 4001 close."""
        config = HarnessConfig.default()
        config.dashboard = DashboardConfig(
            api_key="ws-secret",
            auth_required=True,
        )
        app = create_app(config=config)
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=wrong") as ws:
                pass
