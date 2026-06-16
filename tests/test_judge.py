"""Tests for validation/judge.py - LLM-as-judge."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sharp.harness.validation.judge import LLMJudge
from sharp.harness.core.config import ValidationConfig, LLMConfig
from sharp.harness.core.types import ValidationResult


class TestLLMJudgeInit:
    def test_init(self):
        config = ValidationConfig()
        judge = LLMJudge(config)
        assert judge.config is config

    def test_init_with_custom_model(self):
        config = ValidationConfig(llm_judge_model="gpt-4o")
        judge = LLMJudge(config, llm_config=LLMConfig(model="gpt-4o"))
        assert judge.provider.config.model == "gpt-4o"


class TestLLMJudgeEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_disabled(self):
        config = ValidationConfig(llm_judge_enabled=False)
        judge = LLMJudge(config)
        result = await judge.evaluate("response", "request")
        assert result.passed is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        config = ValidationConfig(llm_judge_enabled=True, min_score=0.7)
        judge = LLMJudge(config)

        mock_response = MagicMock()
        mock_response.content = '{"score": 0.9, "passed": true, "feedback": "Good", "issues": [], "suggestions": []}'
        judge.provider.complete = AsyncMock(return_value=mock_response)

        result = await judge.evaluate("This is a good response.", "What is Python?")
        assert result.passed is True
        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_evaluate_failure(self):
        config = ValidationConfig(llm_judge_enabled=True, min_score=0.7)
        judge = LLMJudge(config)

        mock_response = MagicMock()
        mock_response.content = '{"score": 0.3, "passed": false, "feedback": "Poor", "issues": ["incomplete"], "suggestions": ["add more"]}'
        judge.provider.complete = AsyncMock(return_value=mock_response)

        result = await judge.evaluate("Bad response", "Complex question")
        assert result.passed is False
        assert result.score == 0.3
        assert "incomplete" in result.issues

    @pytest.mark.asyncio
    async def test_evaluate_llm_failure_fallback(self):
        config = ValidationConfig(llm_judge_enabled=True)
        judge = LLMJudge(config)
        judge.provider.complete = AsyncMock(side_effect=Exception("LLM error"))

        result = await judge.evaluate("response", "request")
        assert result.passed is False  # Fail closed on error (HIGH-2 fix)
        assert result.score == 0.0
        assert "failed" in result.feedback.lower()

    @pytest.mark.asyncio
    async def test_evaluate_invalid_json_fallback(self):
        config = ValidationConfig(llm_judge_enabled=True)
        judge = LLMJudge(config)

        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all"
        judge.provider.complete = AsyncMock(return_value=mock_response)

        result = await judge.evaluate("response", "request")
        # Fail closed on invalid JSON (HIGH-2 fix)
        assert result.passed is False
        assert result.score == 0.0
