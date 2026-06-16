"""SHARP harness — public API surface.

This is the recommended import path for users:

    from sharp.harness import Harness, HarnessConfig

Everything else should be treated as internal unless documented in EXTENDING.md.
"""

from sharp.harness.core.engine import HarnessEngine as Harness
from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.types import HarnessResult, ValidationResult
from sharp.harness.core.errors import HarnessError

__all__ = [
    "Harness",
    "HarnessConfig",
    "HarnessResult",
    "ValidationResult",
    "HarnessError",
]
