"""Bridge between SHARP engine and dashboard API responses."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from sharp.harness.dashboard.models import (
    AggregateMetrics,
    BudgetStatus,
    CircuitBreakerStatus,
    ConnectionItem,
    ConnectionMetric,
    ConnectionsResponse,
    ExecutionCurrent,
    ExecutionStep,
    HealthResponse,
    SafetyResponse,
    TraceDetail,
    TimeseriesPoint,
    TimeseriesResponse,
)

if TYPE_CHECKING:
    from sharp.harness.core.engine import HarnessEngine


_start_time = time.time()


def _time_ago(ts: float) -> float:
    return time.time() - ts if ts > 0 else 0


class DashboardBridge:
    """Reads live state from HarnessEngine and formats for dashboard."""

    def __init__(self, engine: HarnessEngine) -> None:
        self.engine = engine
        self._last_run_time: float = 0.0
        self._recent_errors: list[dict] = []

    def record_run(self) -> None:
        self._last_run_time = time.time()

    def record_error(self, error: str) -> None:
        self._recent_errors.append({"error": error, "timestamp": time.time()})
        if len(self._recent_errors) > 20:
            self._recent_errors = self._recent_errors[-20:]

    def get_health(self) -> HealthResponse:
        cb = self.engine.circuit_breaker.get_status()
        mcp_servers = self.engine.mcp_client.connected_servers
        tools_registered = len(self.engine._tools)

        connections_total = 1 + len(mcp_servers) + (1 if tools_registered > 0 else 0)
        connections_healthy = 0
        if cb["state"] in ("closed", "half_open"):
            connections_healthy += 1
        connections_healthy += len(mcp_servers)
        if tools_registered > 0:
            connections_healthy += 1

        return HealthResponse(
            status="running" if cb["state"] != "open" else "degraded",
            uptime_seconds=time.time() - _start_time,
            last_run_seconds_ago=_time_ago(self._last_run_time) if self._last_run_time else None,
            connections_healthy=connections_healthy,
            connections_total=connections_total,
        )

    def get_metrics_aggregate(self) -> AggregateMetrics:
        agg = self.engine.metrics.get_aggregate()
        total = agg["total_traces"]
        failed = agg["failed_traces"]
        return AggregateMetrics(
            total_traces=total,
            successful_traces=agg["successful_traces"],
            failed_traces=failed,
            total_tokens=agg["total_tokens"],
            total_cost=agg["total_cost"],
            avg_latency_ms=agg["avg_latency_ms"],
            success_rate=(agg["successful_traces"] / total * 100) if total > 0 else 100.0,
            error_rate=(failed / total * 100) if total > 0 else 0.0,
        )

    def get_metrics_traces(self) -> list[TraceDetail]:
        traces = self.engine.metrics.get_all_traces()
        return [
            TraceDetail(
                trace_id=t.trace_id,
                latency_ms=t.latency_ms,
                tokens_used=t.tokens_used,
                cost_usd=t.cost_usd,
                success=t.success,
                timestamp=t.start_time,
            )
            for t in traces
        ]

    def get_metrics_timeseries(self, window_minutes: int = 60) -> TimeseriesResponse:
        traces = self.engine.metrics.get_all_traces()
        now = time.time()
        cutoff = now - (window_minutes * 60)

        recent = [t for t in traces if t.start_time >= cutoff]

        if not recent:
            return TimeseriesResponse(points=[])

        bucket_size = max(60, window_minutes * 60 // 12)
        buckets: dict[int, list] = {}
        for t in recent:
            bucket = int((t.start_time - cutoff) // bucket_size)
            buckets.setdefault(bucket, []).append(t)

        points = []
        for i in sorted(buckets.keys()):
            bucket_traces = buckets[i]
            latencies = sorted([t.latency_ms for t in bucket_traces])
            p50_idx = len(latencies) // 2
            p95_idx = int(len(latencies) * 0.95)
            points.append(
                TimeseriesPoint(
                    label=f"{i * bucket_size // 60}m",
                    latency_p50=latencies[p50_idx] if latencies else 0,
                    latency_p95=latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0,
                    throughput=len(bucket_traces),
                    tokens=sum(t.tokens_used for t in bucket_traces),
                    cost=sum(t.cost_usd for t in bucket_traces),
                )
            )

        return TimeseriesResponse(points=points)

    def get_connections(self) -> ConnectionsResponse:
        connections = []

        llm_config = self.engine.config.llm
        provider_status = "connected" if llm_config.api_key else "not_configured"
        provider_label = "Connected" if llm_config.api_key else "Not Configured"
        traces = self.engine.metrics.get_all_traces()
        llm_traces = traces
        avg_lat = (
            sum(t.latency_ms for t in llm_traces) / len(llm_traces)
            if llm_traces
            else 0
        )
        total_tokens = sum(t.tokens_used for t in llm_traces)
        total_cost = sum(t.cost_usd for t in llm_traces)

        connections.append(
            ConnectionItem(
                id="llm",
                name=f"LLM Provider ({llm_config.provider})",
                type="llm",
                status=provider_status,
                status_label=provider_label,
                uptime_pct=99.9 if provider_status == "connected" else 0.0,
                metrics=[
                    ConnectionMetric(label="Latency", value=f"{avg_lat:.0f} ms"),
                    ConnectionMetric(label="Tokens", value=f"{total_tokens:,}"),
                    ConnectionMetric(label="Cost", value=f"${total_cost:.4f}"),
                ],
            )
        )

        mcp_servers = self.engine.mcp_client.connected_servers
        mcp_tools = self.engine.mcp_client.discovered_tools
        mcp_status = "connected" if mcp_servers else "not_configured"
        mcp_label = f"{len(mcp_servers)} connected" if mcp_servers else "No servers"
        connections.append(
            ConnectionItem(
                id="mcp",
                name="MCP Servers",
                type="mcp",
                status=mcp_status,
                status_label=mcp_label,
                uptime_pct=99.0 if mcp_servers else 0.0,
                metrics=[
                    ConnectionMetric(label="Servers", value=str(len(mcp_servers))),
                    ConnectionMetric(label="Tools", value=str(len(mcp_tools))),
                    ConnectionMetric(
                        label="Resources",
                        value=str(len(self.engine.mcp_client.discovered_resources)),
                    ),
                ],
            )
        )

        tools = self.engine._tools
        tools_status = "connected" if tools else "not_configured"
        tools_label = f"{len(tools)} registered" if tools else "No tools"
        blocked = self.engine.config.tools.blocked_tools
        connections.append(
            ConnectionItem(
                id="tools",
                name="Tool Registry",
                type="tools",
                status=tools_status,
                status_label=tools_label,
                uptime_pct=100.0,
                metrics=[
                    ConnectionMetric(label="Registered", value=str(len(tools))),
                    ConnectionMetric(label="Blocked", value=str(len(blocked))),
                    ConnectionMetric(
                        label="Risk Levels",
                        value=", ".join(
                            sorted(set(t.risk_level.value for t in tools))
                        )
                        or "none",
                    ),
                ],
            )
        )

        state_status = "connected" if self.engine.config.state.enabled else "not_configured"
        state_label = self.engine.config.state.backend if self.engine.config.state.enabled else "Disabled"
        connections.append(
            ConnectionItem(
                id="state",
                name="State Backend",
                type="state",
                status=state_status,
                status_label=state_label,
                uptime_pct=100.0 if self.engine.config.state.enabled else 0.0,
                metrics=[
                    ConnectionMetric(label="Backend", value=self.engine.config.state.backend),
                    ConnectionMetric(
                        label="Sessions",
                        value=str(len(self.engine._prior_outputs)),
                    ),
                    ConnectionMetric(label="TTL", value=f"{self.engine.config.state.session_ttl}s"),
                ],
            )
        )

        return ConnectionsResponse(connections=connections)

    def get_execution_current(self) -> ExecutionCurrent:
        loop_state = self.engine.execution_loop.state
        steps = []
        for entry in loop_state.history:
            step = ExecutionStep(
                step_type=entry.get("type", "unknown"),
                content=entry.get("content", ""),
                iteration=entry.get("iteration", 0),
                timestamp=entry.get("timestamp", 0),
            )
            steps.append(step)

        for tc in loop_state.tool_calls:
            step = ExecutionStep(
                step_type="action",
                content=f"Call {tc.get('tool', 'unknown')}",
                iteration=tc.get("iteration", 0),
                timestamp=tc.get("timestamp", 0),
                tool_name=tc.get("tool"),
                tool_args=tc.get("arguments"),
            )
            steps.append(step)

        steps.sort(key=lambda s: s.iteration)

        agg = self.engine.metrics.get_aggregate()

        return ExecutionCurrent(
            active=not loop_state.done and loop_state.iteration > 0,
            iteration=loop_state.iteration,
            steps=steps,
            done=loop_state.done,
            final_answer=loop_state.final_answer,
            strategy=self.engine.config.execution.loop_strategy,
            total_steps=len(steps),
            total_tokens=agg["total_tokens"],
            total_cost=agg["total_cost"],
        )

    def get_safety(self) -> SafetyResponse:
        cb = self.engine.circuit_breaker.get_status()
        budget = self.engine.budget_manager.get_usage()

        return SafetyResponse(
            circuit_breaker=CircuitBreakerStatus(
                state=cb["state"],
                failure_count=cb["failure_count"],
                threshold=cb["threshold"],
                recovery_seconds=cb["recovery_seconds"],
            ),
            budget=BudgetStatus(
                session_tokens=budget["session_tokens"],
                session_cost=budget["session_cost"],
                total_tokens=budget["total_tokens"],
                total_cost=budget["total_cost"],
                token_limit=budget["token_limit"],
                cost_limit=budget["cost_limit"],
                token_usage_pct=budget["token_usage_pct"],
                cost_usage_pct=budget["cost_usage_pct"],
            ),
            recent_errors=list(self._recent_errors[-5:]),
        )
