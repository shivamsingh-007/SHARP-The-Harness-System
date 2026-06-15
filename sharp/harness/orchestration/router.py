"""IntentRouter: decides which AI interface and model to use for each task.

Analyzes task type, complexity, and context to make routing decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sharp.harness.orchestration.types import (
    InterfaceType,
    ModelType,
    RoutingDecision,
    RoutingStrategy,
    TaskComplexity,
    TaskType,
)
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


# ── Routing Rules ──────────────────────────────────────────────────────

ROUTING_TABLE: dict[TaskType, dict[str, Any]] = {
    TaskType.CODING_BUG_FIX: {
        "best_interface": InterfaceType.CLAUDE_CODE,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_SONNET),
            (InterfaceType.CHATGPT_APP, ModelType.GPT4O),
        ],
        "reasoning": "Claude Code has file system access, test runner, and git — best for bug fixes",
        "complexity": TaskComplexity.MEDIUM,
    },
    TaskType.CODING_NEW_FEATURE: {
        "best_interface": InterfaceType.CLAUDE_CODE,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_SONNET),
        ],
        "reasoning": "New features need file access, testing, and iterative development",
        "complexity": TaskComplexity.HIGH,
    },
    TaskType.CODING_REFACTOR: {
        "best_interface": InterfaceType.CLAUDE_CODE,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_SONNET),
            (InterfaceType.CHATGPT_APP, ModelType.GPT4O),
        ],
        "reasoning": "Refactoring benefits from full repo access and test verification",
        "complexity": TaskComplexity.HIGH,
    },
    TaskType.RAG_QUESTION: {
        "best_interface": InterfaceType.CHATGPT_APP,
        "best_model": ModelType.GPT4O_MINI,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_HAIKU),
            (InterfaceType.CLAUDE_CODE, ModelType.CLAUDE_HAIKU),
        ],
        "reasoning": "RAG questions are retrieval-focused, fast response preferred",
        "complexity": TaskComplexity.LOW,
    },
    TaskType.MULTI_STEP_PLANNING: {
        "best_interface": InterfaceType.CLAUDE_APP,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CHATGPT_APP, ModelType.GPT4O),
        ],
        "reasoning": "Claude excels at long reasoning chains and structured planning",
        "complexity": TaskComplexity.HIGH,
    },
    TaskType.QUICK_RESEARCH: {
        "best_interface": InterfaceType.CHATGPT_APP,
        "best_model": ModelType.GPT4O_MINI,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_HAIKU),
        ],
        "reasoning": "Quick research needs fast response, GPT-4o-mini is fast and cheap",
        "complexity": TaskComplexity.LOW,
    },
    TaskType.API_INTEGRATION: {
        "best_interface": InterfaceType.CLAUDE_CODE,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_SONNET),
        ],
        "reasoning": "API integration needs terminal access to test calls",
        "complexity": TaskComplexity.MEDIUM,
    },
    TaskType.COMPLEX_ARCHITECTURE: {
        "best_interface": InterfaceType.CLAUDE_APP,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CHATGPT_APP, ModelType.GPT4O),
        ],
        "reasoning": "Architecture design benefits from Claude's deep reasoning",
        "complexity": TaskComplexity.HIGH,
    },
    TaskType.DOCUMENTATION: {
        "best_interface": InterfaceType.CHATGPT_APP,
        "best_model": ModelType.GPT4O_MINI,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_HAIKU),
        ],
        "reasoning": "Documentation is generation-focused, fast and cheap is fine",
        "complexity": TaskComplexity.LOW,
    },
    TaskType.CODE_REVIEW: {
        "best_interface": InterfaceType.CLAUDE_CODE,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_SONNET),
            (InterfaceType.CHATGPT_APP, ModelType.GPT4O),
        ],
        "reasoning": "Code review needs access to full repo context and file contents",
        "complexity": TaskComplexity.MEDIUM,
    },
    TaskType.TESTING: {
        "best_interface": InterfaceType.CLAUDE_CODE,
        "best_model": ModelType.CLAUDE_SONNET,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_SONNET),
        ],
        "reasoning": "Testing requires running test suites and verifying results",
        "complexity": TaskComplexity.MEDIUM,
    },
    TaskType.GENERAL: {
        "best_interface": InterfaceType.CHATGPT_APP,
        "best_model": ModelType.GPT4O_MINI,
        "alternatives": [
            (InterfaceType.CLAUDE_APP, ModelType.CLAUDE_HAIKU),
        ],
        "reasoning": "General tasks default to fast, cheap model",
        "complexity": TaskComplexity.LOW,
    },
}


# ── Task Classification Keywords ───────────────────────────────────────

TASK_KEYWORDS: dict[TaskType, list[str]] = {
    TaskType.CODING_BUG_FIX: [
        "fix", "bug", "error", "broken", "crash", "issue", "not working",
        "doesn't work", "failing", "fails", "exception", "traceback",
    ],
    TaskType.CODING_NEW_FEATURE: [
        "add", "create", "implement", "new feature", "build", "make",
        "develop", "introduce", "add support",
    ],
    TaskType.CODING_REFACTOR: [
        "refactor", "clean up", "reorganize", "restructure", "simplify",
        "improve code", "code quality", "technical debt",
    ],
    TaskType.RAG_QUESTION: [
        "what is", "how does", "explain", "tell me about", "describe",
        "what are", "how do", "define", "meaning of",
    ],
    TaskType.MULTI_STEP_PLANNING: [
        "plan", "strategy", "roadmap", "approach", "design", "architect",
        "break down", "steps", "phases", "milestones",
    ],
    TaskType.QUICK_RESEARCH: [
        "search", "find", "look up", "research", "latest", "current",
        "recent", "news", "update",
    ],
    TaskType.API_INTEGRATION: [
        "api", "endpoint", "rest", "graphql", "webhook", "integrate",
        "connect", "api call", "request",
    ],
    TaskType.COMPLEX_ARCHITECTURE: [
        "architecture", "system design", "infrastructure", "scalability",
        "microservices", "distributed", "high-level design",
    ],
    TaskType.DOCUMENTATION: [
        "document", "readme", "docs", "documentation", "comment",
        "annotate", "explain code", "write docs",
    ],
    TaskType.CODE_REVIEW: [
        "review", "audit", "check code", "code review", "feedback on",
        "look at this code", "evaluate",
    ],
    TaskType.TESTING: [
        "test", "write test", "test suite", "unit test", "integration test",
        "coverage", "test case", "assertion",
    ],
}


# ── IntentRouter ───────────────────────────────────────────────────────

@dataclass
class IntentRouterConfig:
    """Configuration for the IntentRouter."""

    strategy: RoutingStrategy = RoutingStrategy.BEST_MATCH
    user_preference: InterfaceType | None = None
    user_preference_model: ModelType | None = None
    cost_threshold_usd: float = 0.50
    latency_threshold_ms: float = 5000.0
    custom_rules: dict[str, Any] = field(default_factory=dict)


class IntentRouter:
    """Decides which AI interface and model to use for each task.

    Analyzes:
    - Task type (coding, research, planning, etc.)
    - Complexity (low/medium/high/critical)
    - Available context (files, git, history)
    - User preferences
    - Cost/latency constraints
    """

    def __init__(self, config: IntentRouterConfig | None = None) -> None:
        self.config = config or IntentRouterConfig()

    def route(self, user_prompt: str, context: dict[str, Any] | None = None) -> RoutingDecision:
        """Analyze a user prompt and decide which interface/model to use.

        Args:
            user_prompt: The user's request text.
            context: Optional context (available files, git state, etc.)

        Returns:
            RoutingDecision with recommended interface and model.
        """
        context = context or {}

        # Step 1: Classify task type
        task_type = self._classify_task(user_prompt)

        # Step 2: Assess complexity
        complexity = self._assess_complexity(user_prompt, task_type, context)

        # Step 3: Look up routing rules
        rules = ROUTING_TABLE.get(task_type, ROUTING_TABLE[TaskType.GENERAL])

        # Step 4: Apply strategy
        decision = self._apply_strategy(task_type, complexity, rules, context)

        # Step 5: Apply user preferences if set
        if self.config.user_preference:
            decision.recommended_interface = self.config.user_preference
        if self.config.user_preference_model:
            decision.recommended_model = self.config.user_preference_model

        # Step 6: Apply constraints
        decision = self._apply_constraints(decision)

        logger.info(
            f"Routing: task={task_type.value}, complexity={complexity.value}, "
            f"interface={decision.recommended_interface.value}, "
            f"model={decision.recommended_model.value}"
        )

        return decision

    def _classify_task(self, prompt: str) -> TaskType:
        """Classify the user's task based on keywords and patterns."""
        prompt_lower = prompt.lower()

        # Score each task type by keyword matches
        scores: dict[TaskType, int] = {}
        for task_type, keywords in TASK_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[task_type] = score

        if not scores:
            return TaskType.GENERAL

        # Return highest scoring task type
        return max(scores, key=scores.get)  # type: ignore

    def _assess_complexity(
        self,
        prompt: str,
        task_type: TaskType,
        context: dict[str, Any],
    ) -> TaskComplexity:
        """Assess task complexity based on prompt and context."""
        # Check routing table default
        rules = ROUTING_TABLE.get(task_type, {})
        default_complexity = rules.get("complexity", TaskComplexity.MEDIUM)

        # Adjust based on context signals
        prompt_lower = prompt.lower()

        # Length-based signals
        if len(prompt) > 500:
            return TaskComplexity.HIGH
        if len(prompt) < 50:
            return TaskComplexity.LOW

        # Multi-file signals
        files = context.get("files_involved", [])
        if len(files) > 5:
            return TaskComplexity.HIGH
        if len(files) > 2:
            return TaskComplexity.MEDIUM

        # Complexity keywords
        high_signals = ["multiple", "complex", "refactor", "architecture", "full", "complete"]
        if any(s in prompt_lower for s in high_signals):
            return TaskComplexity.HIGH

        low_signals = ["quick", "simple", "one", "single", "just"]
        if any(s in prompt_lower for s in low_signals):
            return TaskComplexity.LOW

        return default_complexity

    def _apply_strategy(
        self,
        task_type: TaskType,
        complexity: TaskComplexity,
        rules: dict[str, Any],
        context: dict[str, Any],
    ) -> RoutingDecision:
        """Apply the configured routing strategy."""
        best_interface = rules["best_interface"]
        best_model = rules["best_model"]
        reasoning = rules["reasoning"]
        alternatives = [
            (iface, model) for iface, model in rules.get("alternatives", [])
        ]

        if self.config.strategy == RoutingStrategy.BEST_MATCH:
            # Use the table's recommendation
            pass

        elif self.config.strategy == RoutingStrategy.COST_OPTIMIZE:
            # Prefer cheaper models when complexity is low
            if complexity == TaskComplexity.LOW:
                for iface, model in alternatives:
                    if model in (ModelType.GPT4O_MINI, ModelType.CLAUDE_HAIKU):
                        best_interface = iface
                        best_model = model
                        reasoning = f"Cost optimization: {model.value} is sufficient for low complexity"
                        break

        elif self.config.strategy == RoutingStrategy.LATENCY_OPTIMIZE:
            # Prefer faster models
            if complexity in (TaskComplexity.LOW, TaskComplexity.MEDIUM):
                for iface, model in alternatives:
                    if model in (ModelType.GPT4O_MINI, ModelType.CLAUDE_HAIKU):
                        best_interface = iface
                        best_model = model
                        reasoning = f"Latency optimization: {model.value} is faster"
                        break

        elif self.config.strategy == RoutingStrategy.LOAD_BALANCE:
            # Could track usage counts here; for now, rotate through alternatives
            pass

        return RoutingDecision(
            task_type=task_type,
            complexity=complexity,
            recommended_interface=best_interface,
            recommended_model=best_model,
            reasoning=reasoning,
            alternative_interfaces=[iface for iface, _ in alternatives],
            alternative_models=[model for _, model in alternatives],
        )

    def _apply_constraints(self, decision: RoutingDecision) -> RoutingDecision:
        """Apply cost and latency constraints."""
        # Estimate cost based on model
        cost_estimates = {
            ModelType.GPT4O: 0.05,
            ModelType.GPT4O_MINI: 0.01,
            ModelType.GPT4_TURBO: 0.04,
            ModelType.CLAUDE_SONNET: 0.06,
            ModelType.CLAUDE_HAIKU: 0.008,
        }
        decision.estimated_cost_usd = cost_estimates.get(decision.recommended_model, 0.05)

        # Estimate latency based on model + complexity
        base_latency = {
            ModelType.GPT4O: 1000,
            ModelType.GPT4O_MINI: 500,
            ModelType.GPT4_TURBO: 1200,
            ModelType.CLAUDE_SONNET: 1400,
            ModelType.CLAUDE_HAIKU: 400,
        }
        complexity_multiplier = {
            TaskComplexity.LOW: 0.8,
            TaskComplexity.MEDIUM: 1.0,
            TaskComplexity.HIGH: 1.5,
            TaskComplexity.CRITICAL: 2.0,
        }
        base = base_latency.get(decision.recommended_model, 1000)
        mult = complexity_multiplier.get(decision.complexity, 1.0)
        decision.estimated_latency_ms = base * mult

        # If estimated cost exceeds threshold, suggest cheaper alternative
        if decision.estimated_cost_usd > self.config.cost_threshold_usd:
            if decision.alternative_models:
                cheaper = [m for m in decision.alternative_models
                           if cost_estimates.get(m, 1.0) < decision.estimated_cost_usd]
                if cheaper:
                    logger.info(
                        f"Cost constraint: {decision.estimated_cost_usd:.3f} > "
                        f"{self.config.cost_threshold_usd:.3f}, alternatives available"
                    )

        return decision
