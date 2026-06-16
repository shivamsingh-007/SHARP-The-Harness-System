"""Benchmark harness with fixed inputs, reproducible runs, and labeled results.

Labels: mocked, synthetic, local_model, provider_backed.
Metrics: latency (p50/p95/p99), token throughput, cost summary.
Baseline: benchmarks/baseline.json for cross-release comparison.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)

BASELINE_PATH = Path(__file__).parent / "baseline.json"


@dataclass
class BenchmarkRun:
    """Single benchmark measurement."""

    name: str
    latency_ms: float
    label: str  # mocked, synthetic, local_model, provider_backed
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark results."""

    name: str
    label: str
    runs: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    success_rate: float = 1.0


class BenchmarkHarness:
    """Runs benchmarks with fixed inputs and produces reports.

    Usage:
        harness = BenchmarkHarness()
        harness.run("context_curation", label="mocked", func=my_func, arg1=val1)
        report = harness.get_report("context_curation")
        harness.save_baseline()
    """

    def __init__(self) -> None:
        self._runs: dict[str, list[BenchmarkRun]] = {}

    def run(
        self,
        name: str,
        label: str,
        func: Callable[..., Any],
        iterations: int = 10,
        **kwargs: Any,
    ) -> BenchmarkReport:
        """Run a benchmark function multiple times and record results."""
        runs = []
        for _ in range(iterations):
            start = time.time()
            try:
                result = func(**kwargs)
                latency_ms = (time.time() - start) * 1000
                tokens = result.get("tokens", 0) if isinstance(result, dict) else 0
                cost = result.get("cost", 0.0) if isinstance(result, dict) else 0.0
                runs.append(BenchmarkRun(
                    name=name,
                    latency_ms=latency_ms,
                    label=label,
                    tokens=tokens,
                    cost_usd=cost,
                    success=True,
                ))
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                runs.append(BenchmarkRun(
                    name=name,
                    latency_ms=latency_ms,
                    label=label,
                    success=False,
                    metadata={"error": str(e)},
                ))

        if name not in self._runs:
            self._runs[name] = []
        self._runs[name].extend(runs)

        return self._build_report(name, label, runs)

    def run_sync(
        self,
        name: str,
        label: str,
        func: Callable[..., Any],
        iterations: int = 10,
        **kwargs: Any,
    ) -> BenchmarkReport:
        """Run a synchronous benchmark function."""
        return self.run(name, label, func, iterations, **kwargs)

    def get_report(self, name: str) -> BenchmarkReport | None:
        """Get aggregated report for a benchmark name."""
        runs = self._runs.get(name, [])
        if not runs:
            return None
        label = runs[0].label
        return self._build_report(name, label, runs)

    def get_all_reports(self) -> list[BenchmarkReport]:
        """Get reports for all benchmarks."""
        reports = []
        for name, runs in self._runs.items():
            label = runs[0].label
            reports.append(self._build_report(name, label, runs))
        return reports

    def save_baseline(self, path: Path | None = None) -> None:
        """Save current results as baseline for comparison."""
        target = path or BASELINE_PATH
        baseline = {}
        for report in self.get_all_reports():
            baseline[report.name] = {
                "label": report.label,
                "p50_ms": report.p50_ms,
                "p95_ms": report.p95_ms,
                "mean_ms": report.mean_ms,
                "runs": report.runs,
            }
        target.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        logger.info(f"Baseline saved to {target}")

    def load_baseline(self, path: Path | None = None) -> dict[str, Any]:
        """Load baseline for comparison."""
        target = path or BASELINE_PATH
        if target.exists():
            return json.loads(target.read_text(encoding="utf-8"))
        return {}

    def compare_to_baseline(self, path: Path | None = None, tolerance: float = 0.1) -> list[dict[str, Any]]:
        """Compare current results to baseline.

        Returns list of regressions where latency increased beyond tolerance.
        """
        baseline = self.load_baseline(path)
        comparisons = []

        for report in self.get_all_reports():
            base = baseline.get(report.name)
            if not base:
                continue

            base_p50 = base.get("p50_ms", 0)
            if base_p50 > 0:
                change = (report.p50_ms - base_p50) / base_p50
                is_regression = change > tolerance
                comparisons.append({
                    "name": report.name,
                    "baseline_p50_ms": base_p50,
                    "current_p50_ms": report.p50_ms,
                    "change_pct": round(change * 100, 1),
                    "regression": is_regression,
                })

        return comparisons

    def _build_report(self, name: str, label: str, runs: list[BenchmarkRun]) -> BenchmarkReport:
        latencies = [r.latency_ms for r in runs]
        successes = sum(1 for r in runs if r.success)

        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return BenchmarkReport(
            name=name,
            label=label,
            runs=n,
            p50_ms=self._percentile(sorted_lat, 50),
            p95_ms=self._percentile(sorted_lat, 95),
            p99_ms=self._percentile(sorted_lat, 99),
            min_ms=min(latencies) if latencies else 0.0,
            max_ms=max(latencies) if latencies else 0.0,
            mean_ms=statistics.mean(latencies) if latencies else 0.0,
            total_tokens=sum(r.tokens for r in runs),
            total_cost=sum(r.cost_usd for r in runs),
            success_rate=successes / n if n > 0 else 0.0,
        )

    @staticmethod
    def _percentile(sorted_data: list[float], percentile: float) -> float:
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * (percentile / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        d = k - f
        return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])
