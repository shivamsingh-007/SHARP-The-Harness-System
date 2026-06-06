"""Tests for validation/retry.py - Retry engine with feedback mutation."""

import pytest
from sharp.harness.validation.retry import RetryEngine
from sharp.harness.core.config import ValidationConfig
from sharp.harness.core.types import ValidationResult
from sharp.harness.prompt.composer import AugmentedPrompt


class TestRetryEngine:
    @pytest.fixture
    def engine(self):
        return RetryEngine(ValidationConfig())

    def test_mutate_for_retry(self, engine):
        original = AugmentedPrompt(
            system_prompt="You are helpful.",
            user_message="Tell me about X",
            context_summary="Context about X",
            total_tokens=100,
        )
        validation = ValidationResult(
            passed=False,
            score=0.3,
            feedback="Response was incomplete",
            issues=["Missing details"],
            suggestions=["Add more information"],
        )

        mutated = engine.mutate_for_retry(original, validation, attempt=1)

        assert "Previous Attempt Failed" in mutated.system_prompt
        assert "Missing details" in mutated.context_summary
        assert mutated.user_message == original.user_message

    def test_mutate_for_retry_adds_retry_instructions(self, engine):
        original = AugmentedPrompt(
            system_prompt="Be helpful.",
            user_message="Question",
            context_summary="",
            total_tokens=50,
        )
        validation = ValidationResult(passed=False, score=0.5)

        mutated = engine.mutate_for_retry(original, validation, attempt=2)

        assert "Previous Attempt Failed" in mutated.system_prompt
        assert "attempt 2" in mutated.system_prompt.lower() or "Attempt Failed" in mutated.system_prompt

    def test_mutate_preserves_user_message(self, engine):
        original = AugmentedPrompt(
            system_prompt="sys",
            user_message="my question",
            context_summary="ctx",
            total_tokens=50,
        )
        validation = ValidationResult(passed=False, score=0.4)

        mutated = engine.mutate_for_retry(original, validation, attempt=1)
        assert mutated.user_message == "my question"
