"""Structured logging."""

from __future__ import annotations

import logging
import sys
from typing import Any


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """Configure structured logging for the harness system."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger for harness
    harness_logger = logging.getLogger("harness")
    harness_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    harness_logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        harness_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(f"harness.{name}")
