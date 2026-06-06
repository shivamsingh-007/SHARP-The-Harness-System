"""Tests for observability/logging.py - Structured logging."""

import pytest
import logging
from sharp.harness.observability.logging import setup_logging, get_logger


class TestLogging:
    def test_setup_logging(self):
        setup_logging("DEBUG")
        logger = logging.getLogger("harness")
        assert logger.level == logging.DEBUG

    def test_setup_logging_info(self):
        setup_logging("INFO")
        logger = logging.getLogger("harness")
        assert logger.level == logging.INFO

    def test_get_logger(self):
        logger = get_logger("test.module")
        assert logger.name == "harness.test.module"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_different_modules(self):
        l1 = get_logger("module1")
        l2 = get_logger("module2")
        assert l1.name != l2.name
