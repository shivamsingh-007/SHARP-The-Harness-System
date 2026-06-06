"""Benchmark runner for SHARP harness system."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from sharp.harness.core.engine import HarnessEngine
from sharp.harness.core.config import HarnessConfig
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    success: bool = True
    iterations: int = 0
    error: str = ""


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report."""

    results: list[BenchmarkResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    success_rate: float = 0.0

    def add(self, result: BenchmarkResult) -> None:
        self.results.append(result)
        self.total_latency_ms += result.latency_ms
        self.total_tokens += result.tokens_used
        self.total_cost += result.cost_usd
        successes = sum(1 for r in self.results if r.success)
        self.success_rate = successes / len(self.results) if self.results else 0.0

    def summary(self) -> str:
        lines = [
            f"Benchmark Report: {len(self.results)} tests",
            f"  Total Latency: {self.total_latency_ms:.0f}ms",
            f"  Total Tokens: {self.total_tokens}",
            f"  Total Cost: ${self.total_cost:.4f}",
            f"  Success Rate: {self.success_rate:.1%}",
            "",
        ]
        for r in self.results:
            status = "OK" if r.success else "FAIL"
            lines.append(
                f"  [{status}] {r.name}: {r.latency_ms:.0f}ms, "
                f"{r.tokens_used} tokens, ${r.cost_usd:.4f}"
            )
            if r.error:
                lines.append(f"    Error: {r.error}")
        return "\n".join(lines)


async def _benchmark_simple_request(engine: HarnessEngine) -> BenchmarkResult:
    """Benchmark a simple request with no tools."""
    start = time.time()
    try:
        result = await engine.run("What is 2 + 2?")
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="simple_request",
            latency_ms=elapsed,
            tokens_used=result.total_tokens,
            cost_usd=result.total_cost_usd,
            success=result.success,
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="simple_request",
            latency_ms=elapsed,
            success=False,
            error=str(e),
        )


async def _benchmark_context_curation(engine: HarnessEngine) -> BenchmarkResult:
    """Benchmark context curation phase."""
    engine.add_memory("test_key", "test_value" * 100)
    start = time.time()
    try:
        curated = engine.context_curator.curate(
            user_request="Test request with context",
            memory=engine._memory,
            prior_outputs=["previous output " * 50],
        )
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="context_curation",
            latency_ms=elapsed,
            success=True,
            iterations=len(curated.sources),
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="context_curation",
            latency_ms=elapsed,
            success=False,
            error=str(e),
        )


async def _benchmark_prompt_composition(engine: HarnessEngine) -> BenchmarkResult:
    """Benchmark prompt composition phase."""
    from sharp.harness.core.types import ContextSource, DisclosureLevel

    sources = [
        ContextSource(
            name=f"doc_{i}",
            content=f"Content for document {i}. " * 50,
            disclosure_level=DisclosureLevel.DETAIL,
        )
        for i in range(10)
    ]
    start = time.time()
    try:
        prompt = engine.prompt_composer.compose(
            user_request="Test prompt composition",
            context_sources=sources,
            tools=engine._tools,
        )
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="prompt_composition",
            latency_ms=elapsed,
            tokens_used=prompt.total_tokens,
            success=True,
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="prompt_composition",
            latency_ms=elapsed,
            success=False,
            error=str(e),
        )


async def _benchmark_validation(engine: HarnessEngine) -> BenchmarkResult:
    """Benchmark validation phase."""
    start = time.time()
    try:
        result = await engine.validator.validate(
            response="This is a well-structured response that answers the question directly.",
            user_request="Answer the question",
            context="Some context",
        )
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="validation",
            latency_ms=elapsed,
            success=result.passed,
            iterations=1,
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="validation",
            latency_ms=elapsed,
            success=False,
            error=str(e),
        )


async def _benchmark_tool_execution(engine: HarnessEngine) -> BenchmarkResult:
    """Benchmark tool registration and execution."""
    @engine.tool()
    async def bench_tool(x: str) -> str:
        """Benchmark tool."""
        return f"result: {x}"

    start = time.time()
    try:
        result = await engine.tool_registry.execute("bench_tool", {"x": "test"})
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="tool_execution",
            latency_ms=elapsed,
            success=result.success,
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return BenchmarkResult(
            name="tool_execution",
            latency_ms=elapsed,
            success=False,
            error=str(e),
        )


_BENCHMARKS = {
    "simple": [_benchmark_simple_request],
    "context": [_benchmark_context_curation],
    "prompt": [_benchmark_prompt_composition],
    "validation": [_benchmark_validation],
    "tool": [_benchmark_tool_execution],
    "all": [
        _benchmark_context_curation,
        _benchmark_prompt_composition,
        _benchmark_validation,
        _benchmark_tool_execution,
        _benchmark_simple_request,
    ],
}


async def run_benchmark(test: str = "all") -> BenchmarkReport:
    """Run benchmark tests.

    Args:
        test: Which benchmark to run ('all', 'simple', 'context', etc.)

    Returns:
        BenchmarkReport with all results.
    """
    config = HarnessConfig.default()
    config.validation.llm_judge_enabled = False  # Skip LLM judge for benchmarks
    engine = HarnessEngine(config)

    benchmarks = _BENCHMARKS.get(test, _BENCHMARKS["all"])
    report = BenchmarkReport()

    logger.info(f"Running benchmark: {test}")

    for bench_fn in benchmarks:
        result = await bench_fn(engine)
        report.add(result)
        logger.info(f"  {result.name}: {'OK' if result.success else 'FAIL'} ({result.latency_ms:.0f}ms)")

    print(report.summary())
    return report
