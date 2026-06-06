"""Tests for validation zone - comprehensive."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sharp.harness.validation.rules import RuleBasedValidator, Rule
from sharp.harness.validation.judge import LLMJudge
from sharp.harness.validation.validator import ResponseValidator
from sharp.harness.core.types import ValidationResult
from sharp.harness.core.config import ValidationConfig


class TestRuleBasedValidator:
    def test_empty_response_fails(self):
        validator = RuleBasedValidator()
        result = validator.validate("")
        assert not result.passed

    def test_valid_response_passes(self):
        validator = RuleBasedValidator()
        result = validator.validate("This is a valid response with enough content.")
        assert result.passed
        assert result.score > 0.5

    def test_custom_rule(self):
        validator = RuleBasedValidator()
        validator.add_rule(
            Rule(
                name="must_contain_hello",
                check=lambda r: "hello" in r.lower(),
                message="Response must contain 'hello'",
            )
        )
        result = validator.validate("Hello world")
        assert result.passed

        result = validator.validate("Goodbye world")
        assert not result.passed

    def test_schema_validation(self):
        validator = RuleBasedValidator()
        schema = {"type": "object", "required": ["name"]}
        result = validator.validate('{"name": "test"}', schema=schema)
        assert result.passed

        result = validator.validate("not json", schema=schema)
        assert not result.passed

    def test_multiple_rules(self):
        validator = RuleBasedValidator()
        validator.add_rule(Rule(name="r1", check=lambda r: len(r) > 5, message="Too short"))
        validator.add_rule(Rule(name="r2", check=lambda r: "hello" in r.lower(), message="No hello"))

        result = validator.validate("hi")
        assert not result.passed  # Both fail

        result = validator.validate("hello world this is long")
        assert result.passed  # Both pass


class TestValidationConfig:
    def test_default_config(self):
        config = ValidationConfig()
        assert config.enabled is True
        assert config.max_retries == 2
        assert config.min_score == 0.5


class TestLLMJudgeIntegration:
    """Tests for LLM judge with mock provider."""

    @pytest.mark.asyncio
    async def test_judge_enabled_by_default(self):
        config = ValidationConfig()
        assert config.llm_judge_enabled is True

    @pytest.mark.asyncio
    async def test_judge_evaluate_passing(self):
        config = ValidationConfig(llm_judge_enabled=True, min_score=0.7)
        judge = LLMJudge(config)

        mock_response = MagicMock()
        mock_response.content = '{"score": 0.9, "passed": true, "feedback": "Excellent", "issues": [], "suggestions": []}'
        judge.provider.complete = AsyncMock(return_value=mock_response)

        result = await judge.evaluate("A well-written response.", "Question?", context="Context")
        assert result.passed is True
        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_judge_evaluate_failing(self):
        config = ValidationConfig(llm_judge_enabled=True, min_score=0.7)
        judge = LLMJudge(config)

        mock_response = MagicMock()
        mock_response.content = '{"score": 0.2, "passed": false, "feedback": "Poor quality", "issues": ["incomplete", "wrong"], "suggestions": ["rewrite"]}'
        judge.provider.complete = AsyncMock(return_value=mock_response)

        result = await judge.evaluate("Bad", "Complex question")
        assert result.passed is False
        assert "incomplete" in result.issues

    @pytest.mark.asyncio
    async def test_validator_with_judge_combined(self):
        config = ValidationConfig(llm_judge_enabled=True)
        validator = ResponseValidator(config)

        validator.llm_judge.evaluate = AsyncMock(
            return_value=ValidationResult(passed=True, score=0.85, feedback="Good")
        )

        result = await validator.validate(
            "A thorough and accurate response.",
            "What is the capital of France?",
            context="Geography question",
        )
        assert result.passed is True
        assert result.score > 0.5

    @pytest.mark.asyncio
    async def test_validator_strict_mode_skips_judge_on_rule_failure(self):
        config = ValidationConfig(level="strict", llm_judge_enabled=True)
        validator = ResponseValidator(config)

        validator.llm_judge.evaluate = AsyncMock(
            return_value=ValidationResult(passed=True, score=0.9)
        )

        result = await validator.validate("", "Question")
        assert result.passed is False  # Rules fail first, judge not called
        validator.llm_judge.evaluate.assert_not_called()
