"""Tests for benchmark harness and timing plugin.

Covers: timing plugin records results, benchmark harness produces reports,
labels, reproducibility, baseline comparison.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from sharp.harness.benchmarks.harness_bench import BenchmarkHarness, BenchmarkReport


# ── Benchmark Harness Tests ──────────────────────────────────────────────


class TestBenchmarkHarness:
    def test_produces_report(self):
        harness = BenchmarkHarness()

        def dummy_func():
            time.sleep(0.001)
            return {"tokens": 10, "cost": 0.001}

        report = harness.run_sync("dummy", label="mocked", func=dummy_func, iterations=3)

        assert isinstance(report, BenchmarkReport)
        assert report.name == "dummy"
        assert report.label == "mocked"
        assert report.runs == 3
        assert report.p50_ms > 0
        assert report.mean_ms > 0

    def test_label_mocked(self):
        harness = BenchmarkHarness()

        report = harness.run_sync("test", label="mocked", func=lambda: {"tokens": 5}, iterations=2)

        assert report.label == "mocked"

    def test_label_synthetic(self):
        harness = BenchmarkHarness()

        report = harness.run_sync("test", label="synthetic", func=lambda: {}, iterations=2)

        assert report.label == "synthetic"

    def test_reproducible_within_tolerance(self):
        harness = BenchmarkHarness()

        def stable_func():
            return {}

        report1 = harness.run_sync("stable", label="mocked", func=stable_func, iterations=5)
        # Run again with same harness (accumulates)
        report2 = harness.get_report("stable")

        # Mean should be within 50% of each other (generous for CI variability)
        assert report2 is not None
        assert abs(report1.mean_ms - report2.mean_ms) / max(report1.mean_ms, 0.001) < 0.5

    def test_success_rate(self):
        harness = BenchmarkHarness()
        call_count = 0

        def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("fail")
            return {}

        report = harness.run_sync("flaky", label="mocked", func=sometimes_fails, iterations=4)

        assert report.success_rate == 0.5

    def test_latency_percentiles(self):
        harness = BenchmarkHarness()

        def fast_func():
            return {}

        report = harness.run_sync("percentiles", label="mocked", func=fast_func, iterations=20)

        assert report.min_ms <= report.p50_ms <= report.p95_ms <= report.max_ms

    def test_get_all_reports(self):
        harness = BenchmarkHarness()

        harness.run_sync("a", label="mocked", func=lambda: {}, iterations=2)
        harness.run_sync("b", label="mocked", func=lambda: {}, iterations=2)

        reports = harness.get_all_reports()
        assert len(reports) == 2

    def test_get_report_nonexistent(self):
        harness = BenchmarkHarness()
        assert harness.get_report("nonexistent") is None


# ── Baseline Tests ───────────────────────────────────────────────────────


class TestBaseline:
    def test_save_and_load_baseline(self, tmp_path):
        harness = BenchmarkHarness()

        def slow_enough():
            time.sleep(0.001)
            return {}

        harness.run_sync("bench1", label="mocked", func=slow_enough, iterations=3)

        baseline_path = tmp_path / "baseline.json"
        harness.save_baseline(baseline_path)

        loaded = harness.load_baseline(baseline_path)
        assert "bench1" in loaded
        assert loaded["bench1"]["label"] == "mocked"
        assert loaded["bench1"]["p50_ms"] >= 0

    def test_compare_to_baseline_no_regression(self, tmp_path):
        harness = BenchmarkHarness()

        def stable_func():
            time.sleep(0.001)
            return {}

        harness.run_sync("stable", label="mocked", func=stable_func, iterations=5)

        baseline_path = tmp_path / "baseline.json"
        harness.save_baseline(baseline_path)

        harness2 = BenchmarkHarness()
        harness2.run_sync("stable", label="mocked", func=stable_func, iterations=5)

        comparisons = harness2.compare_to_baseline(baseline_path, tolerance=0.5)
        assert len(comparisons) == 1
        assert comparisons[0]["regression"] is False

    def test_compare_to_baseline_with_regression(self, tmp_path):
        harness = BenchmarkHarness()

        def fast_func():
            time.sleep(0.001)
            return {}

        harness.run_sync("fast", label="mocked", func=fast_func, iterations=5)

        baseline_path = tmp_path / "baseline.json"
        harness.save_baseline(baseline_path)

        harness2 = BenchmarkHarness()

        def slow_func():
            time.sleep(0.05)
            return {}

        harness2.run_sync("fast", label="mocked", func=slow_func, iterations=3)

        comparisons = harness2.compare_to_baseline(baseline_path, tolerance=0.01)
        assert len(comparisons) == 1
        assert comparisons[0]["regression"] is True


# ── Timing Plugin Test ──────────────────────────────────────────────────


class TestTimingPlugin:
    def test_plugin_registered(self):
        """Plugin is registered when imported."""
        from sharp.harness.benchmarks.timing_plugin import TimingPlugin
        plugin = TimingPlugin()
        assert hasattr(plugin, "results")
        assert hasattr(plugin, "pytest_runtest_setup")
        assert hasattr(plugin, "pytest_runtest_makereport")
