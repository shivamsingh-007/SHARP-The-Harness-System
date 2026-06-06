"""Configuration models for the harness system."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from sharp.harness.core.types import DisclosureLevel, LoopStrategy, RiskLevel, ValidationLevel


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_key: str | None = None
    api_base: str | None = None
    timeout: float = 60.0


class ContextLayerConfig(BaseModel):
    """Configuration for a context layer."""

    name: str
    source: str  # file path or callable name
    source_type: str = "file"  # "file", "callable", "static"
    priority: int = 0
    disclosure_level: DisclosureLevel = DisclosureLevel.INDEX
    keywords: list[str] = Field(default_factory=list)
    token_budget: int | None = None
    freshness_seconds: int | None = None  # Max age in seconds


class ContextConfig(BaseModel):
    """Context engineering zone configuration."""

    layers: list[ContextLayerConfig] = Field(default_factory=list)
    total_token_budget: int = 8000
    compression_threshold: float = 0.8  # Compress when usage > 80%
    dedup_threshold: float = 0.85  # Semantic similarity for dedup


class PromptConfig(BaseModel):
    """Prompt engineering zone configuration."""

    system_prompt_template: str = "default"
    include_tools_in_prompt: bool = True
    include_memory_in_prompt: bool = True
    max_context_tokens: int = 6000
    reserved_output_tokens: int = 2000


class ToolConfig(BaseModel):
    """Tool governance configuration."""

    risk_levels: dict[str, RiskLevel] = Field(default_factory=dict)
    blocked_tools: list[str] = Field(default_factory=list)
    max_output_tokens: int = 2000
    require_approval_for: list[RiskLevel] = Field(
        default_factory=lambda: [RiskLevel.EXECUTE, RiskLevel.CRITICAL]
    )


class ValidationConfig(BaseModel):
    """Validation zone configuration."""

    enabled: bool = True
    level: ValidationLevel = ValidationLevel.LENIENT
    llm_judge_enabled: bool = True
    llm_judge_model: str = "gpt-4o-mini"
    rules: list[dict[str, Any]] = Field(default_factory=list)
    min_score: float = 0.5
    max_retries: int = 2


class SafetyConfig(BaseModel):
    """Safety layer configuration."""

    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_seconds: float = 60.0
    budget_enabled: bool = True
    max_cost_usd: float = 10.0
    max_tokens: int = 100000
    blocked_commands: list[str] = Field(default_factory=list)
    approval_mode: str = "risky_only"  # "all", "risky_only", "none"


class StateConfig(BaseModel):
    """State persistence configuration."""

    enabled: bool = True
    backend: str = "file"  # "file", "redis"
    checkpoint_dir: str = ".harness/checkpoints"
    session_ttl: int = 3600  # 1 hour
    redis_url: str | None = None


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    tracing_enabled: bool = False
    metrics_enabled: bool = True
    logging_level: str = "INFO"
    otlp_endpoint: str | None = None
    log_file: str | None = None


class ExecutionConfig(BaseModel):
    """Execution layer configuration."""

    loop_strategy: LoopStrategy = LoopStrategy.REACT
    max_iterations: int = 10
    timeout: float = 120.0


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    name: str
    command: str | None = None  # for stdio transport (e.g., "npx", "python")
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None  # for http/sse transport
    transport: str = "stdio"  # "stdio" | "http"
    enabled: bool = True
    description: str = ""


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""

    enabled: bool = True
    servers: list[MCPServerConfig] = Field(default_factory=list)
    auto_discover: bool = True  # auto-connect and discover tools/resources on engine init
    connect_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    tool_risk_overrides: dict[str, str] = Field(default_factory=dict)  # tool_name -> risk_level


class HarnessConfig(BaseModel):
    """Top-level harness configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> HarnessConfig:
        """Load configuration from a YAML file.

        Supports ${VAR_NAME} environment variable expansion in string values.
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        if data:
            data = cls._expand_env_vars(data)
            return cls(**data)
        return cls()

    @staticmethod
    def _expand_env_vars(obj: Any) -> Any:
        """Recursively expand ${VAR_NAME} patterns in string values."""
        if isinstance(obj, str):
            pattern = re.compile(r"\$\{(\w+)\}")
            def replacer(match: re.Match) -> str:
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            return pattern.sub(replacer, obj)
        elif isinstance(obj, dict):
            return {k: HarnessConfig._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [HarnessConfig._expand_env_vars(item) for item in obj]
        return obj

    @classmethod
    def default(cls) -> HarnessConfig:
        """Return default configuration."""
        return cls()
