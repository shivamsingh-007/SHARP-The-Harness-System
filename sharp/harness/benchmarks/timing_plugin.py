"""Pytest plugin for per-test timing and outcome recording.

Writes results to test-results.json after the test suite completes.
Fields per entry: test_name, duration_ms, outcome, timestamp.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest


class TimingPlugin:
    """Records test timing and outcome."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self._start_times: dict[str, float] = {}

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        self._start_times[item.nodeid] = time.time()

    @pytest.hookimpl
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo[None]) -> None:
        if call.when == "call":
            start = self._start_times.pop(item.nodeid, time.time())
            duration_ms = (time.time() - start) * 1000

            if call.excinfo is None:
                outcome = "passed"
            else:
                outcome = "failed"

            self.results.append({
                "test_name": item.nodeid,
                "duration_ms": round(duration_ms, 2),
                "outcome": outcome,
                "timestamp": time.time(),
            })

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        output_path = Path("test-results.json")
        output_path.write_text(
            json.dumps(self.results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def pytest_configure(config: pytest.Config) -> None:
    plugin = TimingPlugin()
    config._timing_plugin = plugin  # type: ignore
    config.pluginmanager.register(plugin, "timing-plugin")
