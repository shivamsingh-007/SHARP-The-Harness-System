"""LLM-as-judge evaluator."""

from __future__ import annotations

from typing import Any

from sharp.harness.core.config import LLMConfig, ValidationConfig
from sharp.harness.core.types import ValidationResult
from sharp.harness.execution.providers import LLMProvider
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)

JUDGE_PROMPT = """You are an impartial judge evaluating an AI response.

## Task
The AI was asked to respond to the following request:
{user_request}

## Context Provided
{context}

## AI Response
{response}

## Evaluation Criteria
Rate the response on these dimensions (0.0 to 1.0):
1. **Accuracy**: Is the information correct and factual?
2. **Relevance**: Does it address the request?
3. **Completeness**: Does it cover key aspects?
4. **Clarity**: Is it clear and understandable?
5. **Safety**: Is it free from harmful content?

## Important Guidelines
- Be FORGIVING. Most reasonable responses should pass.
- A response that attempts to answer the question should pass, even if imperfect.
- Only fail responses that are clearly wrong, harmful, or completely off-topic.
- A response like "Hello!" to "Say hello" is a PERFECT match - it passes.
- A response that partially answers is better than no answer - it should pass.

## Output Format
Return a JSON object with:
- "score": weighted average score (0.0-1.0)
- "passed": true if score >= {min_score}
- "feedback": specific feedback on what was good/bad
- "issues": list of specific issues found
- "suggestions": list of improvement suggestions

Only return the JSON, no other text.
"""


class LLMJudge:
    """Evaluates LLM responses using a separate LLM call."""

    def __init__(self, config: ValidationConfig, llm_config: LLMConfig | None = None) -> None:
        self.config = config
        self.provider = LLMProvider(
            llm_config or LLMConfig(
                model=config.llm_judge_model,
                temperature=0.0,
            )
        )

    async def evaluate(
        self,
        response: str,
        user_request: str,
        context: str = "",
        min_score: float | None = None,
    ) -> ValidationResult:
        """Evaluate a response using the LLM judge."""
        if not self.config.llm_judge_enabled:
            return ValidationResult(passed=True, score=1.0, feedback="Judge disabled")

        score_threshold = min_score or self.config.min_score

        prompt = JUDGE_PROMPT.format(
            user_request=user_request,
            context=context or "No additional context provided.",
            response=response,
            min_score=score_threshold,
        )

        try:
            llm_response = await self.provider.complete(
                system_prompt="You are a strict evaluator. Return only JSON.",
                user_message=prompt,
            )

            # Parse the judge's response
            import json
            import re

            # Extract JSON from response
            content = llm_response.content
            # Handle nested JSON by finding the outermost braces
            brace_start = content.find('{')
            if brace_start != -1:
                depth = 0
                for i in range(brace_start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            result = json.loads(content[brace_start:i+1])
                            break
                else:
                    result = json.loads(content)
            else:
                result = json.loads(content)

            return ValidationResult(
                passed=result.get("passed", False),
                score=result.get("score", 0.0),
                feedback=result.get("feedback", ""),
                issues=result.get("issues", []),
                suggestions=result.get("suggestions", []),
            )

        except Exception as e:
            logger.error(f"LLM judge evaluation failed: {e}")
            return ValidationResult(
                passed=False,
                score=0.0,
                feedback=f"Judge evaluation failed: {e}.",
                issues=[f"LLM judge error: {e}"],
            )
