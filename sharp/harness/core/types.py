"""Shared types and enums for the harness system."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Tool risk classification levels."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    CRITICAL = "critical"


class DisclosureLevel(str, Enum):
    """Context layer disclosure levels."""

    INDEX = "index"  # Always loaded - summary/overview
    DETAIL = "detail"  # Loaded on demand - full content


class ValidationLevel(str, Enum):
    """Validation strictness levels."""

    STRICT = "strict"  # All checks must pass
    LENIENT = "lenient"  # Critical checks only
    NONE = "none"  # Skip validation


class LoopStrategy(str, Enum):
    """Execution loop strategies."""

    REACT = "react"  # Reason + Act (standard)
    COT = "cot"  # Chain of Thought
    TOT = "tot"  # Tree of Thoughts


class ToolDefinition(BaseModel):
    """Definition of a tool available to the LLM."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.READ
    requires_approval: bool = False
    timeout: float = 30.0


class ToolResult(BaseModel):
    """Result from a tool execution."""

    tool_name: str
    success: bool
    output: str
    error: str | None = None
    duration_ms: float = 0.0
    tokens_used: int = 0


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str
    model: str
    provider: str
    tokens_used: int = 0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str = ""


class ValidationResult(BaseModel):
    """Result from validation."""

    passed: bool
    score: float = 0.0  # 0.0 - 1.0
    feedback: str = ""
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ContextSource(BaseModel):
    """A source of context information."""

    name: str
    content: str
    source_type: str  # "user", "memory", "tool_output", "retrieved_doc"
    priority: int = 0  # Lower = higher priority
    token_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessResult(BaseModel):
    """Final result from the harness engine.

    Returned by HarnessEngine.run(). Fields are stable across v0.x releases.

    Attributes:
        success: Whether the pipeline completed without fatal error.
        output: The final text output from the LLM or tool.
        attempts: Number of execution attempts (1 = no retries).
        total_latency_ms: Wall-clock time for the full pipeline.
        total_cost_usd: Estimated cost in USD (0.0 for local models).
        total_tokens: Total tokens consumed (prompt + completion).
        validation_score: Score from the validation zone (0.0–1.0).
        error: Error message if success is False, else None.
        trace_id: Unique identifier for this execution trace.
    """

    success: bool
    output: str
    attempts: int = 1
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    validation_score: float = 0.0
    error: str | None = None
    trace_id: str | None = None
