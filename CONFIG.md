# Configuration

All SHARP configuration fields, defaults, and environment variables.

## Quick reference

```python
from sharp.harness import HarnessConfig

# GitHub Models (recommended for quickstart)
config = HarnessConfig.github_models(model="gpt-4o-mini")

# Ollama (local, no API key)
config = HarnessConfig.ollama(model="llama3.1:8b")

# Default (OpenAI gpt-4o)
config = HarnessConfig.default()

# From YAML file
config = HarnessConfig.from_yaml("harness.yaml")
```

## Precedence

1. Explicit Python constructor args
2. Environment variables (where documented)
3. YAML file values
4. Defaults

## LLM

| Field | Type | Default | Effect |
|---|---|---|---|
| `llm.provider` | str | `"openai"` | LiteLLM provider name |
| `llm.model` | str | `"gpt-4o"` | Model ID |
| `llm.temperature` | float | `0.7` | Sampling temperature |
| `llm.max_tokens` | int | `4096` | Max completion tokens |
| `llm.api_key` | str \| None | None | Provider API key |
| `llm.api_base` | str \| None | None | Custom API base URL |
| `llm.timeout` | float | `60.0` | Request timeout (seconds) |

## Context

| Field | Type | Default | Effect |
|---|---|---|---|
| `context.layers` | list | `[]` | Context layers to curate |
| `context.total_token_budget` | int | `8000` | Max tokens across all layers |
| `context.compression_threshold` | float | `0.8` | Trigger compression at this ratio |
| `context.dedup_threshold` | float | `0.85` | Dedup similarity threshold |

## Prompt

| Field | Type | Default | Effect |
|---|---|---|---|
| `prompt.system_prompt_template` | str | `"default"` | System prompt template |
| `prompt.include_tools_in_prompt` | bool | `True` | Inject tool definitions |
| `prompt.include_memory_in_prompt` | bool | `True` | Inject memory |
| `prompt.max_context_tokens` | int | `6000` | Max context tokens |
| `prompt.reserved_output_tokens` | int | `2000` | Tokens reserved for output |

## Tools

| Field | Type | Default | Effect |
|---|---|---|---|
| `tools.risk_levels` | dict | `{}` | Custom risk overrides |
| `tools.blocked_tools` | list | `[]` | Tool names to block |
| `tools.max_output_tokens` | int | `2000` | Max tool output tokens |
| `tools.require_approval_for` | list | `[EXECUTE, CRITICAL]` | Risk levels needing approval |

## Validation

| Field | Type | Default | Effect |
|---|---|---|---|
| `validation.enabled` | bool | `True` | Enable validation |
| `validation.level` | enum | `LENIENT` | `STRICT`, `LENIENT`, or `NONE` |
| `validation.llm_judge_enabled` | bool | `True` | Enable LLM judge |
| `validation.llm_judge_model` | str | `"gpt-4o-mini"` | Judge model |
| `validation.min_score` | float | `0.5` | Minimum score to pass |
| `validation.max_retries` | int | `2` | Max retry attempts |

## Safety

| Field | Type | Default | Effect |
|---|---|---|---|
| `safety.circuit_breaker_enabled` | bool | `True` | Enable circuit breaker |
| `safety.failure_threshold` | int | `5` | Failures before breaker opens |
| `safety.recovery_seconds` | float | `60.0` | Cooldown before half-open |
| `safety.budget_enabled` | bool | `True` | Enable budget limits |
| `safety.max_cost_usd` | float | `10.0` | Hard cost limit |
| `safety.max_tokens` | int | `100000` | Hard token limit |

## Execution

| Field | Type | Default | Effect |
|---|---|---|---|
| `execution.loop_strategy` | enum | `REACT` | `REACT`, `COT`, or `TOT` |
| `execution.max_iterations` | int | `10` | Max loop iterations |
| `execution.timeout` | float | `120.0` | Total execution timeout |
| `execution.loop_policy` | str | `"auto"` | `"auto"`, `"always_react"`, `"never_react"` |

## Dashboard

| Field | Type | Default | Env var | Effect |
|---|---|---|---|---|
| `dashboard.api_key` | str \| None | None | `SHARP_API_KEY` | API auth key |
| `dashboard.auth_required` | bool | `True` | — | Require auth on `/api/*` |
| `dashboard.dev_mode` | bool | `False` | — | Disable all auth/CORS/rate-limit |
| `dashboard.cors_origins` | list | `["http://localhost:3000", ...]` | — | Allowed origins |
| `dashboard.rate_limit_enabled` | bool | `True` | — | Enable rate limiting |
| `dashboard.rate_limit_rpm` | int | `60` | — | General requests/min |
| `dashboard.rate_limit_expensive_rpm` | int | `10` | — | Expensive endpoint RPM |

## State

| Field | Type | Default | Effect |
|---|---|---|---|
| `state.enabled` | bool | `True` | Enable persistence |
| `state.backend` | str | `"file"` | `"file"` or `"redis"` |
| `state.checkpoint_dir` | str | `".harness/checkpoints"` | Storage path |
| `state.session_ttl` | int | `3600` | Session TTL (seconds) |
| `state.redis_url` | str \| None | None | Redis URL |

## Observability

| Field | Type | Default | Effect |
|---|---|---|---|
| `observability.tracing_enabled` | bool | `False` | Enable tracing |
| `observability.metrics_enabled` | bool | `True` | Enable metrics |
| `observability.logging_level` | str | `"INFO"` | Log level |
| `observability.otlp_endpoint` | str \| None | None | OpenTelemetry endpoint |
| `observability.log_file` | str \| None | None | Structured log file |

## MCP

| Field | Type | Default | Effect |
|---|---|---|---|
| `mcp.enabled` | bool | `True` | Enable MCP |
| `mcp.servers` | list | `[]` | MCP server configs |
| `mcp.auto_discover` | bool | `True` | Auto-discover tools |
| `mcp.connect_timeout` | float | `30.0` | Connection timeout |

### MCP server config

```python
config.mcp.servers = [
    {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
        "transport": "stdio",
    },
]
```

## YAML example

```yaml
llm:
  provider: openai
  model: gpt-4o
  temperature: 0.7
  max_tokens: 2048

validation:
  enabled: true
  level: strict
  max_retries: 3
  min_score: 0.7

safety:
  circuit_breaker_enabled: true
  failure_threshold: 5
  max_cost_usd: 10.0
  max_tokens: 100000
```

```python
config = HarnessConfig.from_yaml("harness.yaml")
```

## Stability

- **Stable** fields documented here will not change without a minor version bump.
- **Experimental** fields may change without notice.
- Breaking config changes require migration notes in CHANGELOG.md.

See [docs/CONFIG_CONTRACT.md](docs/CONFIG_CONTRACT.md) for the full contract.
