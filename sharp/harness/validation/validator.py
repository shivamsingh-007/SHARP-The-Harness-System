"""Combined response validator orchestrator."""

from __future__ import annotations

from sharp.harness.core.config import ValidationConfig
from sharp.harness.core.types import ValidationResult
from sharp.harness.validation.judge import LLMJudge
from sharp.harness.validation.rules import RuleBasedValidator
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class ResponseValidator:
    """Orchestrates validation using both LLM judge and rule-based checks.

    Combines:
    - Rule-based validation (deterministic, fast)
    - LLM-as-judge (semantic, slower but more nuanced)
    """

    def __init__(self, config: ValidationConfig) -> None:
        self.config = config
        self.rule_validator = RuleBasedValidator()
        self.llm_judge = LLMJudge(config)

    def validate(
        self,
        response: str,
        user_request: str,
        context: str = "",
    ) -> ValidationResult:
        """Validate a response using all available validators.

        Runs rule-based validation first (fast), then LLM judge if enabled.
        """
        if not self.config.enabled:
            return ValidationResult(passed=True, score=1.0, feedback="Validation disabled")

        if self.config.level.value == "none":
            return ValidationResult(passed=True, score=1.0, feedback="Validation skipped")

        # Phase 1: Rule-based validation
        rule_result = self.rule_validator.validate(response)

        # If strict mode and rules fail, skip LLM judge
        if self.config.level.value == "strict" and not rule_result.passed:
            logger.info(f"Strict validation failed: {rule_result.issues}")
            return rule_result

        # Phase 2: LLM judge (if enabled and rules passed or lenient mode)
        if self.config.llm_judge_enabled:
            # Run LLM judge asynchronously
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        judge_result = pool.submit(
                            asyncio.run,
                            self.llm_judge.evaluate(
                                response=response,
                                user_request=user_request,
                                context=context,
                            ),
                        ).result()
                else:
                    judge_result = asyncio.run(
                        self.llm_judge.evaluate(
                            response=response,
                            user_request=user_request,
                            context=context,
                        )
                    )
            except Exception as e:
                logger.warning(f"LLM judge failed: {e}")
                judge_result = ValidationResult(
                    passed=True,
                    score=0.7,
                    feedback=f"Judge failed: {e}",
                )

            # Combine results
            combined_score = (rule_result.score + judge_result.score) / 2
            combined_passed = rule_result.passed and judge_result.passed
            combined_issues = rule_result.issues + judge_result.issues
            combined_suggestions = rule_result.suggestions + judge_result.suggestions

            return ValidationResult(
                passed=combined_passed,
                score=combined_score,
                feedback=f"Rules: {rule_result.feedback} | Judge: {judge_result.feedback}",
                issues=combined_issues,
                suggestions=combined_suggestions,
            )

        return rule_result
