"""Core types for SHARP Universal Orchestration Layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class InterfaceType(str, Enum):
    """Which AI interface the user is interacting through."""

    CLAUDE_APP = "claude_app"
    CHATGPT_APP = "chatgpt_app"
    CLAUDE_CODE = "claude_code"
    CUSTOM_API = "custom_api"
    COPILOT = "copilot"
    VSCODE_AI = "vscode_ai"
    CURSOR = "cursor"
    WINDSURF = "windsurf"


class TaskType(str, Enum):
    """Classification of user task."""

    CODING_BUG_FIX = "coding_bug_fix"
    CODING_NEW_FEATURE = "coding_new_feature"
    CODING_REFACTOR = "coding_refactor"
    RAG_QUESTION = "rag_question"
    MULTI_STEP_PLANNING = "multi_step_planning"
    QUICK_RESEARCH = "quick_research"
    API_INTEGRATION = "api_integration"
    COMPLEX_ARCHITECTURE = "complex_architecture"
    DOCUMENTATION = "documentation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    GENERAL = "general"


class ModelType(str, Enum):
    """Backend AI models available."""

    CLAUDE_SONNET = "claude-sonnet-4-20250514"
    CLAUDE_HAIKU = "claude-3-5-haiku-20241022"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT4_TURBO = "gpt-4-turbo"
    CUSTOM = "custom"


class RoutingStrategy(str, Enum):
    """How the intent router selects a model/interface."""

    BEST_MATCH = "best_match"  # Always pick the optimal model
    LOAD_BALANCE = "load_balance"  # Distribute across models
    COST_OPTIMIZE = "cost_optimize"  # Pick cheapest adequate model
    LATENCY_OPTIMIZE = "latency_optimize"  # Pick fastest model
    USERPreference = "user_preference"  # Respect user's explicit choice


class TaskComplexity(str, Enum):
    """Complexity level for routing decisions."""

    LOW = "low"  # Simple lookup, quick question
    MEDIUM = "medium"  # Moderate reasoning, some context needed
    HIGH = "high"  # Deep reasoning, multi-file, multi-step
    CRITICAL = "critical"  # Production, safety-sensitive


@dataclass
class RoutingDecision:
    """Decision from the IntentRouter about which model/interface to use."""

    task_type: TaskType
    complexity: TaskComplexity
    recommended_interface: InterfaceType
    recommended_model: ModelType
    reasoning: str
    estimated_latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    alternative_interfaces: list[InterfaceType] = field(default_factory=list)
    alternative_models: list[ModelType] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class InterfaceRequest:
    """Normalized request from any AI interface."""

    interface: InterfaceType
    user_prompt: str
    task_type: TaskType | None = None
    context: dict[str, Any] = field(default_factory=dict)
    files_involved: list[str] = field(default_factory=list)
    repo_url: str | None = None
    branch: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InterfaceResponse:
    """Normalized response from any AI interface."""

    success: bool
    output: str
    interface: InterfaceType
    model: ModelType
    latency_ms: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    validation_passed: bool = True
    validation_score: float = 1.0
    validation_issues: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_total: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ContextAggregation:
    """Merged context from all sources for a request."""

    task_description: str
    relevant_files: list[str] = field(default_factory=list)
    file_contents: dict[str, str] = field(default_factory=dict)
    git_diff: str = ""
    git_log: str = ""
    previous_sessions: list[str] = field(default_factory=list)
    interface_histories: dict[str, list[str]] = field(default_factory=dict)
    progress_summary: str = ""
    feature_state: dict[str, Any] = field(default_factory=dict)
    tool_outputs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """Complete trace of a single orchestration request."""

    trace_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_prompt: str = ""
    interface: InterfaceType = InterfaceType.CUSTOM_API
    routing_decision: RoutingDecision | None = None
    context_used: ContextAggregation | None = None
    model_used: ModelType = ModelType.CUSTOM
    ai_output: str = ""
    validation_result: dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    latency_ms: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    final_status: str = "pending"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance metrics for dashboard display."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_requests: int = 0
    avg_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    success_rate: float = 0.0
    hallucination_rate: float = 0.0
    avg_retries: float = 0.0
    model_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    interface_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_requests: list[dict[str, Any]] = field(default_factory=list)
