"""Tests for validation zone."""

import pytest
from sharp.harness.validation.rules import RuleBasedValidator, Rule
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


class TestValidationConfig:
    def test_default_config(self):
        config = ValidationConfig()
        assert config.enabled is True
        assert config.max_retries == 3
        assert config.min_score == 0.7
