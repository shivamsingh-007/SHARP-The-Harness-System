"""Rule-based validators."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from sharp.harness.core.types import ValidationResult
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class Rule:
    """A validation rule."""

    def __init__(
        self,
        name: str,
        check: Callable[[str], bool],
        message: str,
        severity: str = "error",
    ) -> None:
        self.name = name
        self.check = check
        self.message = message
        self.severity = severity


class RuleBasedValidator:
    """Validates responses against a set of rules."""

    def __init__(self) -> None:
        self._rules: list[Rule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register default validation rules."""
        self.add_rule(
            Rule(
                name="not_empty",
                check=lambda r: bool(r.strip()),
                message="Response is empty",
                severity="error",
            )
        )
        self.add_rule(
            Rule(
                name="min_length",
                check=lambda r: len(r.strip()) >= 10,
                message="Response is too short (minimum 10 characters)",
                severity="warning",
            )
        )
        self.add_rule(
            Rule(
                name="no_hallucination_markers",
                check=lambda r: not any(
                    marker in r.lower()
                    for marker in ["as an ai", "i don't have access", "i cannot verify"]
                ),
                message="Response contains hallucination markers",
                severity="warning",
            )
        )

    def add_rule(self, rule: Rule) -> None:
        """Add a validation rule."""
        self._rules.append(rule)

    def validate(
        self,
        response: str,
        schema: dict[str, Any] | None = None,
        required_fields: list[str] | None = None,
    ) -> ValidationResult:
        """Validate a response against all rules."""
        issues = []
        suggestions = []
        all_passed = True

        for rule in self._rules:
            try:
                if not rule.check(response):
                    all_passed = False
                    if rule.severity == "error":
                        issues.append(f"[ERROR] {rule.name}: {rule.message}")
                    else:
                        suggestions.append(f"[WARN] {rule.name}: {rule.message}")
            except Exception as e:
                logger.warning(f"Rule '{rule.name}' check failed: {e}")

        # Schema validation if provided
        if schema:
            schema_result = self._validate_schema(response, schema)
            if not schema_result["valid"]:
                all_passed = False
                issues.append(f"[ERROR] schema: {schema_result['message']}")

        # Required fields validation
        if required_fields:
            for field in required_fields:
                if field.lower() not in response.lower():
                    suggestions.append(f"[INFO] Missing recommended field: {field}")

        # Calculate score
        total_rules = len(self._rules) + (1 if schema else 0)
        passed_rules = sum(
            1 for rule in self._rules
            if self._safe_check(rule, response)
        ) + (1 if not schema or self._validate_schema(response, schema)["valid"] else 0)

        score = passed_rules / total_rules if total_rules > 0 else 1.0

        return ValidationResult(
            passed=all_passed,
            score=score,
            feedback=f"Passed {passed_rules}/{total_rules} rules",
            issues=issues,
            suggestions=suggestions,
        )

    def _validate_schema(self, response: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Validate response against a JSON schema."""
        try:
            # Try to parse as JSON
            data = json.loads(response)

            # Check required fields
            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    return {"valid": False, "message": f"Missing required field: {field}"}

            return {"valid": True, "message": ""}

        except json.JSONDecodeError:
            # Not JSON - check if schema expects JSON
            if schema.get("type") == "object":
                return {"valid": False, "message": "Response is not valid JSON"}
            return {"valid": True, "message": ""}

    def _safe_check(self, rule: Rule, response: str) -> bool:
        """Safely run a rule check."""
        try:
            return rule.check(response)
        except Exception:
            return True
