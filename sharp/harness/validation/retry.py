"""Retry engine with feedback mutation."""

from __future__ import annotations

from dataclasses import dataclass

from sharp.harness.core.config import ValidationConfig
from sharp.harness.core.types import ValidationResult
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AugmentedPrompt:
    """Placeholder for augmented prompt (imported from prompt.composer)."""

    system_prompt: str
    user_message: str
    context_summary: str
    total_tokens: int = 0
    sections: dict | None = None


class RetryEngine:
    """Manages retry logic with context mutation.

    When validation fails, the retry engine:
    1. Analyzes the failure
    2. Mutates the context (add error feedback, adjust tools)
    3. Returns mutated prompt for retry
    """

    def __init__(self, config: ValidationConfig) -> None:
        self.config = config

    def mutate_for_retry(
        self,
        original_prompt: AugmentedPrompt,
        validation_result: ValidationResult,
        attempt: int,
    ) -> AugmentedPrompt:
        """Mutate the prompt for retry based on validation failure.

        Adds error feedback and suggestions to the context.
        """
        logger.info(f"Mutating prompt for retry attempt {attempt}")

        # Build error feedback
        feedback_parts = [
            f"## Previous Attempt Failed (attempt {attempt})",
            f"Score: {validation_result.score:.2f}",
        ]

        if validation_result.issues:
            feedback_parts.append("\n### Issues Found")
            for issue in validation_result.issues:
                feedback_parts.append(f"- {issue}")

        if validation_result.suggestions:
            feedback_parts.append("\n### Suggestions")
            for suggestion in validation_result.suggestions:
                feedback_parts.append(f"- {suggestion}")

        if validation_result.feedback:
            feedback_parts.append(f"\n### Feedback\n{validation_result.feedback}")

        feedback = "\n".join(feedback_parts)

        # Add feedback to context
        new_context = original_prompt.context_summary
        if new_context:
            new_context = f"{new_context}\n\n{feedback}"
        else:
            new_context = feedback

        # Enhance system prompt with retry instructions
        retry_instruction = (
            "\n\n## Important: Previous Attempt Failed\n"
            "Your previous response did not pass validation. Please:\n"
            "1. Review the issues and suggestions above\n"
            "2. Address each issue explicitly\n"
            "3. Ensure your response is complete and accurate\n"
            "4. Do not repeat the same mistakes\n"
        )

        new_system = original_prompt.system_prompt + retry_instruction

        return AugmentedPrompt(
            system_prompt=new_system,
            user_message=original_prompt.user_message,
            context_summary=new_context,
            total_tokens=0,  # Will be recalculated
            sections=original_prompt.sections,
        )
