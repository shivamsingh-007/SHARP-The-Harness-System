"""Validate repo metrics against documented claims.

Run in CI to prevent documentation drift.
Exits with code 1 if any metric diverges by >10% from expected.
"""

from __future__ import annotations

import sys
from pathlib import Path


EXPECTED = {
    "source_files": 73,
    "source_lines": 10871,
    "test_files": 38,
    "test_lines": 6349,
}

TOLERANCE = 0.10  # 10%


def count_python_files(directory: Path) -> int:
    return len(list(directory.rglob("*.py")))


def count_lines(directory: Path) -> int:
    total = 0
    for f in directory.rglob("*.py"):
        try:
            total += len(f.read_text(encoding="utf-8").splitlines())
        except Exception:
            continue
    return total


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    sharp_dir = root / "sharp"
    tests_dir = root / "tests"

    actual = {
        "source_files": count_python_files(sharp_dir),
        "source_lines": count_lines(sharp_dir),
        "test_files": count_python_files(tests_dir) - 1,  # exclude conftest.py
        "test_lines": count_lines(tests_dir),
    }

    errors = []
    for key, expected_val in EXPECTED.items():
        actual_val = actual[key]
        if expected_val == 0:
            continue
        delta = abs(actual_val - expected_val) / expected_val
        if delta > TOLERANCE:
            errors.append(
                f"  {key}: expected ~{expected_val}, got {actual_val} "
                f"(delta: {delta:.1%})"
            )

    if errors:
        print("Metric drift detected (>10% divergence):")
        for e in errors:
            print(e)
        print("\nUpdate EXPECTED in scripts/check_repo_metrics.py")
        return 1

    print("All metrics within tolerance.")
    for key in EXPECTED:
        print(f"  {key}: {actual[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
