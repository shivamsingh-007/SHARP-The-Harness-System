"""Tests for validation/validator.py - Response validator orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sharp.harness.validation.validator import ResponseValidator
from sharp.harness.core.config import ValidationConfig
from sharp.harness.core.types import ValidationResult, ValidationLevel


class TestResponseValidator:
    @pytest.fixture
    def validator(self):
        config = ValidationConfig(llm_judge_enabled=False)
        return ResponseValidator(config)

    @pytest.fixture
    def validator_with_judge(self):
        config = ValidationConfig(llm_judge_enabled=True)
        return ResponseValidator(config)

    @pytest.mark.asyncio
    async def test_validate_disabled(self):
        config = ValidationConfig(enabled=False)
        v = ResponseValidator(config)
        result = await v.validate("response", "request")
        assert result.passed is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_validate_strict_pass(self, validator):
        result = await validator.validate(
            "This is a valid response with enough content to pass.",
            "Answer the question",
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_strict_fail(self, validator):
        result = await validator.validate("", "Answer the question")
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_validate_lenient_mode(self):
        config = ValidationConfig(level=ValidationLevel.LENIENT, llm_judge_enabled=False)
        v = ResponseValidator(config)
        result = await v.validate(
            "This is a sufficiently long response that passes the minimum length requirement.",
            "Question",
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_with_llm_judge(self, validator_with_judge):
        # Mock the LLM judge to return a passing result
        validator_with_judge.llm_judge.evaluate = AsyncMock(
            return_value=ValidationResult(passed=True, score=0.85, feedback="Good")
        )
        result = await validator_with_judge.validate(
            "A complete and accurate response.",
            "What is Python?",
            context="Programming language",
        )
        assert result.passed is True
        assert result.score > 0.5

    @pytest.mark.asyncio
    async def test_validate_llm_judge_failure(self, validator_with_judge):
        validator_with_judge.llm_judge.evaluate = AsyncMock(
            side_effect=Exception("LLM error")
        )
        result = await validator_with_judge.validate(
            "A valid response.",
            "Question",
        )
        # Should still pass because rules pass and judge failure is caught
        assert result.passed is True
