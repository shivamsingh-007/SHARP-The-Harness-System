"""Pydantic models for dashboard API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "running"
    uptime_seconds: float = 0.0
    last_run_seconds_ago: float | None = None
    environment: str = "development"
    connections_healthy: int = 0
    connections_total: int = 0
    version: str = "0.1.0"


class AggregateMetrics(BaseModel):
    total_traces: int = 0
    successful_traces: int = 0
    failed_traces: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0


class TraceDetail(BaseModel):
    trace_id: str
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    success: bool = True
    timestamp: float = 0.0


class TimeseriesPoint(BaseModel):
    label: str
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    throughput: int = 0
    tokens: int = 0
    cost: float = 0.0


class TimeseriesResponse(BaseModel):
    points: list[TimeseriesPoint] = Field(default_factory=list)


class ConnectionMetric(BaseModel):
    label: str
    value: str


class ConnectionItem(BaseModel):
    id: str
    name: str
    type: str
    status: str = "disconnected"
    status_label: str = "Not Configured"
    metrics: list[ConnectionMetric] = Field(default_factory=list)
    uptime_pct: float = 100.0


class ConnectionsResponse(BaseModel):
    connections: list[ConnectionItem] = Field(default_factory=list)


class ExecutionStep(BaseModel):
    step_type: str
    content: str
    iteration: int = 0
    timestamp: float = 0.0
    duration_ms: float = 0.0
    tool_name: str | None = None
    tool_args: dict | None = None


class ExecutionCurrent(BaseModel):
    active: bool = False
    iteration: int = 0
    steps: list[ExecutionStep] = Field(default_factory=list)
    done: bool = False
    final_answer: str = ""
    strategy: str = "react"
    total_steps: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    started_at: float | None = None


class CircuitBreakerStatus(BaseModel):
    state: str = "closed"
    failure_count: int = 0
    threshold: int = 5
    recovery_seconds: float = 60.0


class BudgetStatus(BaseModel):
    session_tokens: int = 0
    session_cost: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    token_limit: int = 100000
    cost_limit: float = 10.0
    token_usage_pct: float = 0.0
    cost_usage_pct: float = 0.0


class SafetyResponse(BaseModel):
    circuit_breaker: CircuitBreakerStatus = Field(default_factory=CircuitBreakerStatus)
    budget: BudgetStatus = Field(default_factory=BudgetStatus)
    recent_errors: list[dict] = Field(default_factory=list)


class WSMessage(BaseModel):
    type: str
    data: dict = Field(default_factory=dict)
