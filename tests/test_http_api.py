"""Tests for SHARP HTTP API endpoints.

Covers: POST /api/route, POST /api/validate, POST /api/coding/session
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from sharp.harness.dashboard.server import create_app
from sharp.harness.core.config import HarnessConfig
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
        assert 0.0 <= data["score"] <= 1.0


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
        assert data["status"] == "started"
        assert data["session_id"] == 1

    def test_coding_session_returns_feature(self, client_with_project):
        test_client, tmp_path = client_with_project
        response = test_client.post("/api/coding/session", json={
            "project_root": str(tmp_path),
            "session_id": 1,
        })
        data = response.json()
        assert "feature" in data
        assert "progress" in data

    def test_coding_session_invalid_project(self, client):
        response = client.post("/api/coding/session", json={
            "project_root": "/nonexistent/path",
            "session_id": 1,
        })
        data = response.json()
        # start_session catches errors internally; the endpoint returns started
        # but with empty features/progress
        assert data["status"] == "started"
        assert data["feature"] is None
