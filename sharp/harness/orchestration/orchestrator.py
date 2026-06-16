"""Orchestrator: main entry point for SHARP Universal Orchestration.

Ties together IntentRouter, InterfaceAdapters, ContextAggregator,
SHARP's validation/retry, and audit logging into a single unified flow.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sharp.harness.core.engine import HarnessEngine
from sharp.harness.core.config import HarnessConfig
from sharp.harness.orchestration.types import (
    AuditEntry,
    ContextAggregation,
    InterfaceRequest,
    InterfaceResponse,
    InterfaceType,
    ModelType,
    PerformanceSnapshot,
    RoutingDecision,
    TaskType,
)
from sharp.harness.orchestration.router import IntentRouter, IntentRouterConfig
from sharp.harness.orchestration.adapters import get_adapter, InterfaceAdapter
from sharp.harness.orchestration.aggregator import ContextAggregator, AggregatorConfig
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the Orchestrator."""

    project_root: str = "."
    enable_validation: bool = True
    enable_audit_log: bool = True
    max_retries: int = 2
    router_config: IntentRouterConfig = field(default_factory=IntentRouterConfig)
    aggregator_config: AggregatorConfig = field(default_factory=AggregatorConfig)
    engine_config: HarnessConfig | None = None


class Orchestrator:
    """SHARP Universal Orchestration Layer.

    Single entry point that:
    1. Receives request from any AI interface
    2. Routes to best model via IntentRouter
    3. Aggregates context from all sources
    4. Executes via SHARP engine with validation
    5. Returns normalized response to originating interface
    6. Logs everything for audit and performance tracking
    """

    def __init__(self, config: OrchestratorConfig | None = None) -> None:
        self.config = config or OrchestratorConfig()
        self.router = IntentRouter(self.config.router_config)
        self.aggregator = ContextAggregator(self.config.aggregator_config)
        self._adapters: dict[InterfaceType, InterfaceAdapter] = {}
        self._audit_log: list[AuditEntry] = []
        self._performance: _PerformanceTracker = _PerformanceTracker()
        self._engine: HarnessEngine | None = None

    def get_adapter(self, interface: InterfaceType) -> InterfaceAdapter:
        """Get or create an adapter for the given interface."""
        if interface not in self._adapters:
            self._adapters[interface] = get_adapter(interface)
        return self._adapters[interface]

    async def handle_request(
        self,
        raw_request: dict[str, Any],
        interface: InterfaceType = InterfaceType.CUSTOM_API,
        interface_type: str | InterfaceType | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Main entry point: handle a request from any AI interface.

        Args:
            raw_request: Raw request dict from the interface.
            interface: Which interface the request came from.
            interface_type: Backward-compat alias for `interface`.

        Returns:
            Normalized response dict for the originating interface.
        """
        if interface_type is not None:
            if isinstance(interface_type, str):
                interface = InterfaceType(interface_type)
            else:
                interface = interface_type
        trace_id = str(uuid.uuid4())[:12]
        adapter = self.get_adapter(interface)

        logger.info(f"[{trace_id}] Handling request from {interface.value}")

        # Step 1: Normalize request
        request = adapter.normalize_request(raw_request)
        logger.info(f"[{trace_id}] Normalized: {request.user_prompt[:80]}...")

        # Step 2: Route to best model
        routing_decision = self.router.route(
            request.user_prompt,
            context={"files_involved": request.files_involved, **request.context},
        )
        logger.info(
            f"[{trace_id}] Routed to {routing_decision.recommended_model.value} "
            f"via {routing_decision.recommended_interface.value}"
        )

        # Step 3: Aggregate context
        aggregation = self.aggregator.aggregate(request)

        # Step 4: Execute via SHARP engine (with validation + retry)
        start_time = datetime.now(timezone.utc)
        response = await self._execute_with_sharp(
            request=request,
            aggregation=aggregation,
            routing_decision=routing_decision,
            trace_id=trace_id,
        )
        end_time = datetime.now(timezone.utc)

        # Step 5: Record in interface history
        self.aggregator.record_interface_history(
            interface,
            request.user_prompt,
            response.output[:100] if response.output else "",
        )

        # Step 6: Audit log
        if self.config.enable_audit_log:
            audit_entry = self._build_audit_entry(
                trace_id=trace_id,
                request=request,
                routing_decision=routing_decision,
                aggregation=aggregation,
                response=response,
            )
            self._audit_log.append(audit_entry)

        # Step 7: Update performance metrics
        self._performance.record(response)

        # Step 8: Format response for originating interface
        formatted = adapter.format_response(response)
        logger.info(
            f"[{trace_id}] Completed: success={response.success}, "
            f"latency={response.latency_ms:.0f}ms, "
            f"cost=${response.cost_usd:.4f}"
        )

        return formatted

    async def _execute_with_sharp(
        self,
        request: InterfaceRequest,
        aggregation: ContextAggregation,
        routing_decision: RoutingDecision,
        trace_id: str,
    ) -> InterfaceResponse:
        """Execute the request through SHARP's engine with validation."""
        start_time = datetime.now(timezone.utc)

        # Build the prompt with aggregated context
        prompt = self._build_prompt(request, aggregation)

        # Create or reuse engine with config matching the routing decision
        if self._engine is None:
            if self.config.engine_config:
                engine_config = self.config.engine_config.model_copy(deep=True)
            else:
                engine_config = HarnessConfig.default()
            engine_config.llm.model = routing_decision.recommended_model.value
            engine_config.validation.enabled = self.config.enable_validation
            self._engine = HarnessEngine(engine_config)
        else:
            # Update model for this request without mutating shared config
            self._engine.config.llm.model = routing_decision.recommended_model.value
            self._engine.config.validation.enabled = self.config.enable_validation

        engine = self._engine

        # Execute with retry
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await engine.run(prompt)

                end_time = datetime.now(timezone.utc)
                latency_ms = (end_time - start_time).total_seconds() * 1000

                return InterfaceResponse(
                    success=result.success,
                    output=result.output,
                    interface=request.interface,
                    model=routing_decision.recommended_model,
                    latency_ms=latency_ms,
                    tokens_input=result.total_tokens // 2 if result.total_tokens else len(prompt) // 4,
                    tokens_output=result.total_tokens // 2 if result.total_tokens else 100,
                    cost_usd=result.total_cost_usd,
                    retries=attempt,
                    validation_passed=result.validation_score >= 0.5 if result.validation_score else True,
                    validation_score=result.validation_score or 1.0,
                    error=result.error,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[{trace_id}] Attempt {attempt + 1} failed: {last_error}")

        # All attempts failed
        end_time = datetime.now(timezone.utc)
        return InterfaceResponse(
            success=False,
            output="",
            interface=request.interface,
            model=routing_decision.recommended_model,
            latency_ms=(end_time - start_time).total_seconds() * 1000,
            error=last_error,
            retries=self.config.max_retries,
            validation_passed=False,
        )

    def _build_prompt(
        self,
        request: InterfaceRequest,
        aggregation: ContextAggregation,
    ) -> str:
        """Build a complete prompt from request + aggregated context."""
        parts = [request.user_prompt]

        if aggregation.relevant_files:
            parts.append(f"\nRelevant files: {', '.join(aggregation.relevant_files)}")

        if aggregation.git_diff:
            parts.append(f"\nRecent changes:\n{aggregation.git_diff[:500]}")

        if aggregation.progress_summary:
            parts.append(f"\nPrevious progress:\n{aggregation.progress_summary[:500]}")

        if aggregation.feature_state:
            parts.append(f"\nFeature state: {aggregation.feature_state}")

        # Add interface histories
        for iface, history in aggregation.interface_histories.items():
            if history:
                recent = "\n".join(history[-3:])
                parts.append(f"\n{iface} history:\n{recent}")

        return "\n".join(parts)

    def _build_audit_entry(
        self,
        trace_id: str,
        request: InterfaceRequest,
        routing_decision: RoutingDecision,
        aggregation: ContextAggregation,
        response: InterfaceResponse,
    ) -> AuditEntry:
        """Build a complete audit entry for this request."""
        return AuditEntry(
            trace_id=trace_id,
            timestamp=request.timestamp,
            user_prompt=request.user_prompt,
            interface=request.interface,
            routing_decision=routing_decision,
            context_used=aggregation,
            model_used=response.model,
            ai_output=response.output,
            validation_result={
                "passed": response.validation_passed,
                "score": response.validation_score,
                "issues": response.validation_issues,
            },
            retries=response.retries,
            latency_ms=response.latency_ms,
            tokens={
                "input": response.tokens_input,
                "output": response.tokens_output,
            },
            cost_usd=response.cost_usd,
            final_status="success" if response.success else "error",
            error=response.error,
        )

    # ── Public Query Methods ───────────────────────────────────────────

    def get_audit_log(
        self,
        interface: InterfaceType | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        """Get audit log entries, optionally filtered by interface."""
        entries = self._audit_log
        if interface:
            entries = [e for e in entries if e.interface == interface]
        return entries[-limit:]

    def get_performance(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        return self._performance.snapshot()

    def get_performance_by_model(self) -> dict[str, dict[str, Any]]:
        """Get performance breakdown by model."""
        return self._performance.by_model()

    def get_performance_by_interface(self) -> dict[str, dict[str, Any]]:
        """Get performance breakdown by interface."""
        return self._performance.by_interface()


class _PerformanceTracker:
    """Internal performance tracking."""

    def __init__(self) -> None:
        self._responses: list[InterfaceResponse] = []

    def record(self, response: InterfaceResponse) -> None:
        """Record a response for performance tracking."""
        self._responses.append(response)
        # Keep last 1000
        if len(self._responses) > 1000:
            self._responses = self._responses[-1000:]

    def snapshot(self) -> PerformanceSnapshot:
        """Generate a performance snapshot."""
        if not self._responses:
            return PerformanceSnapshot()

        total = len(self._responses)
        successes = sum(1 for r in self._responses if r.success)
        total_latency = sum(r.latency_ms for r in self._responses)
        total_cost = sum(r.cost_usd for r in self._responses)
        total_retries = sum(r.retries for r in self._responses)
        validation_failures = sum(1 for r in self._responses if not r.validation_passed)

        recent = self._responses[-10:]
        recent_list = [
            {
                "model": r.model.value,
                "interface": r.interface.value,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd,
                "validation_passed": r.validation_passed,
            }
            for r in recent
        ]

        return PerformanceSnapshot(
            total_requests=total,
            avg_latency_ms=total_latency / total if total else 0,
            total_cost_usd=total_cost,
            success_rate=successes / total if total else 0,
            hallucination_rate=validation_failures / total if total else 0,
            avg_retries=total_retries / total if total else 0,
            model_breakdown=self.by_model(),
            interface_breakdown=self.by_interface(),
            recent_requests=recent_list,
        )

    def by_model(self) -> dict[str, dict[str, Any]]:
        """Break down metrics by model."""
        by_model: dict[str, list[InterfaceResponse]] = {}
        for r in self._responses:
            key = r.model.value
            if key not in by_model:
                by_model[key] = []
            by_model[key].append(r)

        result = {}
        for model, responses in by_model.items():
            total = len(responses)
            successes = sum(1 for r in responses if r.success)
            result[model] = {
                "requests": total,
                "avg_latency_ms": sum(r.latency_ms for r in responses) / total,
                "success_rate": successes / total,
                "hallucination_rate": sum(1 for r in responses if not r.validation_passed) / total,
                "total_cost_usd": sum(r.cost_usd for r in responses),
            }
        return result

    def by_interface(self) -> dict[str, dict[str, Any]]:
        """Break down metrics by interface."""
        by_iface: dict[str, list[InterfaceResponse]] = {}
        for r in self._responses:
            key = r.interface.value
            if key not in by_iface:
                by_iface[key] = []
            by_iface[key].append(r)

        result = {}
        for iface, responses in by_iface.items():
            total = len(responses)
            successes = sum(1 for r in responses if r.success)
            result[iface] = {
                "requests": total,
                "avg_latency_ms": sum(r.latency_ms for r in responses) / total,
                "success_rate": successes / total,
                "hallucination_rate": sum(1 for r in responses if not r.validation_passed) / total,
                "total_cost_usd": sum(r.cost_usd for r in responses),
            }
        return result
