"""AuditLogger: persistent JSON trace of every orchestration decision.

Logs every request, routing decision, context used, output, validation
result, retries, and performance metrics to a JSON-lines file.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sharp.harness.orchestration.types import (
    AuditEntry,
    InterfaceType,
    InterfaceResponse,
    ModelType,
    RoutingDecision,
)
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AuditLoggerConfig:
    """Configuration for the AuditLogger."""

    log_dir: str = ".harness/audit"
    log_file: str = "audit_log.jsonl"
    max_entries_in_memory: int = 1000
    enable_console_output: bool = False


class AuditLogger:
    """Persistent audit logger that writes every decision to JSON-lines.

    Features:
    - Append-only JSON-lines file (no file corruption on crash)
    - In-memory buffer for fast queries
    - Filter by interface, model, status, time range
    - Export to JSON for dashboard consumption
    """

    def __init__(self, config: AuditLoggerConfig | None = None) -> None:
        self.config = config or AuditLoggerConfig()
        self._log_dir = Path(self.config.log_dir)
        self._log_file = self._log_dir / self.config.log_file
        self._memory_buffer: list[dict[str, Any]] = []

        # Ensure log directory exists
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        """Write an audit entry to the log.

        Args:
            entry: The complete audit entry to log.
        """
        record = self._entry_to_dict(entry)

        # Write to file (append)
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        # Keep in memory buffer
        self._memory_buffer.append(record)
        if len(self._memory_buffer) > self.config.max_entries_in_memory:
            self._memory_buffer = self._memory_buffer[-self.config.max_entries_in_memory:]

        # Optional console output
        if self.config.enable_console_output:
            status = "✅" if record.get("final_status") == "success" else "❌"
            model = record.get("model_used", "unknown")
            latency = record.get("latency_ms", 0)
            cost = record.get("cost_usd", 0)
            logger.info(
                f"{status} [{model}] {latency:.0f}ms ${cost:.4f} "
                f"- {record.get('user_prompt', '')[:60]}"
            )

    def log_response(
        self,
        trace_id: str,
        response: InterfaceResponse,
        routing_decision: RoutingDecision | None = None,
        user_prompt: str = "",
        interface: InterfaceType = InterfaceType.CUSTOM_API,
    ) -> None:
        """Convenience method: log an InterfaceResponse directly.

        Builds an AuditEntry from the response and logs it.
        """
        entry = AuditEntry(
            trace_id=trace_id,
            user_prompt=user_prompt,
            interface=interface,
            routing_decision=routing_decision,
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
        self.log(entry)

    def query(
        self,
        interface: InterfaceType | None = None,
        model: ModelType | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query audit log entries from memory buffer.

        Args:
            interface: Filter by interface type.
            model: Filter by model type.
            status: Filter by final_status ("success" or "error").
            limit: Max entries to return.

        Returns:
            List of audit records matching filters.
        """
        entries = list(self._memory_buffer)

        if interface:
            entries = [e for e in entries if e.get("interface") == interface.value]
        if model:
            entries = [e for e in entries if e.get("model_used") == model.value]
        if status:
            entries = [e for e in entries if e.get("final_status") == status]

        return entries[-limit:]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all logged entries."""
        entries = self._memory_buffer
        if not entries:
            return {"total": 0}

        total = len(entries)
        successes = sum(1 for e in entries if e.get("final_status") == "success")
        total_cost = sum(e.get("cost_usd", 0) for e in entries)
        total_latency = sum(e.get("latency_ms", 0) for e in entries)
        total_retries = sum(e.get("retries", 0) for e in entries)

        # Model breakdown
        by_model: dict[str, int] = {}
        for e in entries:
            model = e.get("model_used", "unknown")
            by_model[model] = by_model.get(model, 0) + 1

        # Interface breakdown
        by_interface: dict[str, int] = {}
        for e in entries:
            iface = e.get("interface", "unknown")
            by_interface[iface] = by_interface.get(iface, 0) + 1

        return {
            "total": total,
            "successes": successes,
            "errors": total - successes,
            "success_rate": successes / total if total else 0,
            "total_cost_usd": total_cost,
            "avg_latency_ms": total_latency / total if total else 0,
            "total_retries": total_retries,
            "by_model": by_model,
            "by_interface": by_interface,
        }

    def export_json(self, path: str | None = None) -> str:
        """Export all audit entries as a single JSON file.

        Args:
            path: Optional path to write to. If None, returns JSON string.

        Returns:
            JSON string of all entries.
        """
        data = json.dumps(self._memory_buffer, indent=2, default=str)
        if path:
            Path(path).write_text(data, encoding="utf-8")
        return data

    def _entry_to_dict(self, entry: AuditEntry) -> dict[str, Any]:
        """Convert AuditEntry to a JSON-serializable dict."""
        d = asdict(entry)

        # Convert enums to strings
        if "interface" in d and hasattr(d["interface"], "value"):
            d["interface"] = d["interface"].value
        if "model_used" in d and hasattr(d["model_used"], "value"):
            d["model_used"] = d["model_used"].value

        # Convert routing decision
        if d.get("routing_decision"):
            rd = d["routing_decision"]
            if hasattr(rd, "task_type"):
                rd["task_type"] = rd["task_type"].value if hasattr(rd["task_type"], "value") else str(rd["task_type"])
                rd["complexity"] = rd["complexity"].value if hasattr(rd["complexity"], "value") else str(rd["complexity"])
                rd["recommended_interface"] = rd["recommended_interface"].value if hasattr(rd["recommended_interface"], "value") else str(rd["recommended_interface"])
                rd["recommended_model"] = rd["recommended_model"].value if hasattr(rd["recommended_model"], "value") else str(rd["recommended_model"])

        # Convert context aggregation
        if d.get("context_used"):
            ctx = d["context_used"]
            if "metadata" in ctx and isinstance(ctx["metadata"], dict):
                # Ensure metadata is JSON-serializable
                ctx["metadata"] = {k: str(v) for k, v in ctx["metadata"].items()}

        return d
