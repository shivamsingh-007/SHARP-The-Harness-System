# Config Contract

Authoritative reference for all SHARP configuration fields, defaults, env vars, and stability guarantees.

## Stability promise

- **Stable** fields are documented here and will not change without a minor version bump.
- **Experimental** fields may change or be removed without notice.
- **Internal** fields exist for framework use; do not rely on them.
- Breaking config changes require a minor version bump and migration notes.

## Canonical sources (precedence)

1. Explicit Python constructor args
2. Environment variables (where documented)
3. YAML file values (`HarnessConfig.from_yaml()`)
4. Defaults (shown below)

## Public API

```python
from sharp.harness import Harness, HarnessConfig, HarnessResult, ValidationResult, HarnessError
```

Everything else should be treated as internal unless documented in [EXTENDING.md](EXTENDING.md).

## Minimal configs

### Minimal Python

```python
from sharp.harness import HarnessConfig
config = HarnessConfig.github_models(model="gpt-4o-mini")
```

### Minimal YAML

```yaml
llm:
  model: gpt-4o
  temperature: 0.7
```

```python
config = HarnessConfig.from_yaml("harness.yaml")
```

### Secure API config

```python
import os
from sharp.harness import HarnessConfig

config = HarnessConfig(
    dashboard=DashboardConfig(
        api_key=os.environ["SHARP_API_KEY"],
        auth_required=True,
        rate_limit_enabled=True,
    ),
)
```

## Compatibility examples

### Valid config

```python
config = HarnessConfig(
    llm=LLMConfig(model="gpt-4o", temperature=0.5),
    validation=ValidationConfig(min_score=0.7),
)
# Works: known fields, valid types
```

### Invalid config (unknown field)

```python
config = HarnessConfig(unknown_field="value")
# Raises ValidationError: extra fields not permitted
```

### Deprecated field warning

```python
# If a field is renamed, the old name emits a warning for one minor version
# then raises an error in the next minor version.
```

## Field tables

### LLMConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `provider` | str | `"openai"` | Stable | LiteLLM provider name |
| `model` | str | `"gpt-4o"` | Stable | Model ID (e.g. `"gpt-4o-mini"`, `"claude-3-5-sonnet"`) |
| `temperature` | float | `0.7` | Stable | Sampling temperature |
| `max_tokens` | int | `4096` | Stable | Max completion tokens |
| `api_key` | str \| None | None | Stable | Provider API key |
| `api_base` | str \| None | None | Stable | Custom API base URL |
| `timeout` | float | `60.0` | Stable | Request timeout in seconds |

### ContextConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `layers` | list | `[]` | Stable | Context layers to curate |
| `total_token_budget` | int | `8000` | Stable | Max tokens across all layers |
| `compression_threshold` | float | `0.8` | Experimental | Trigger compression at this ratio |
| `dedup_threshold` | float | `0.85` | Experimental | Dedup similarity threshold |

### PromptConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `system_prompt_template` | str | `"default"` | Stable | System prompt template name |
| `include_tools_in_prompt` | bool | `True` | Stable | Inject tool definitions into prompt |
| `include_memory_in_prompt` | bool | `True` | Stable | Inject memory into prompt |
| `max_context_tokens` | int | `6000` | Stable | Max context tokens for prompt |
| `reserved_output_tokens` | int | `2000` | Stable | Tokens reserved for output |

### ToolConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `risk_levels` | dict | `{}` | Stable | Custom risk level overrides |
| `blocked_tools` | list | `[]` | Stable | Tool names to block |
| `max_output_tokens` | int | `2000` | Stable | Max tool output tokens |
| `require_approval_for` | list | `[EXECUTE, CRITICAL]` | Stable | Risk levels requiring HITL approval |

### ValidationConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `enabled` | bool | `True` | Stable | Enable validation zone |
| `level` | ValidationLevel | `LENIENT` | Stable | `STRICT`, `LENIENT`, or `NONE` |
| `llm_judge_enabled` | bool | `True` | Stable | Enable LLM-as-judge |
| `llm_judge_model` | str | `"gpt-4o-mini"` | Stable | Model used for judging |
| `rules` | list | `[]` | Stable | Custom validation rules |
| `min_score` | float | `0.5` | Stable | Minimum score to pass |
| `max_retries` | int | `2` | Stable | Max retry attempts on failure |

### SafetyConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `circuit_breaker_enabled` | bool | `True` | Stable | Enable circuit breaker |
| `failure_threshold` | int | `5` | Stable | Failures before breaker opens |
| `recovery_seconds` | float | `60.0` | Stable | Cooldown before half-open |
| `budget_enabled` | bool | `True` | Stable | Enable budget limits |
| `max_cost_usd` | float | `10.0` | Stable | Hard cost limit per engine |
| `max_tokens` | int | `100000` | Stable | Hard token limit per engine |
| `blocked_commands` | list | `[]` | Stable | Subprocess commands to block |
| `approval_mode` | str | `"risky_only"` | Stable | `"all"`, `"risky_only"`, or `"none"` |

### StateConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `enabled` | bool | `True` | Stable | Enable state persistence |
| `backend` | str | `"file"` | Stable | `"file"` or `"redis"` |
| `checkpoint_dir` | str | `".harness/checkpoints"` | Stable | Checkpoint storage path |
| `session_ttl` | int | `3600` | Stable | Session TTL in seconds |
| `redis_url` | str \| None | None | Stable | Redis connection URL |

### ObservabilityConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `tracing_enabled` | bool | `False` | Stable | Enable distributed tracing |
| `metrics_enabled` | bool | `True` | Stable | Enable metrics collection |
| `logging_level` | str | `"INFO"` | Stable | Log level |
| `otlp_endpoint` | str \| None | None | Stable | OpenTelemetry endpoint |
| `log_file` | str \| None | None | Stable | File path for structured logs |

### ExecutionConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `loop_strategy` | LoopStrategy | `REACT` | Stable | `REACT`, `COT`, or `TOT` |
| `max_iterations` | int | `10` | Stable | Max ReAct loop iterations |
| `timeout` | float | `120.0` | Stable | Total execution timeout |
| `loop_policy` | str | `"auto"` | Experimental | `"auto"`, `"always_react"`, `"never_react"` |

### MCPConfig

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `enabled` | bool | `True` | Stable | Enable MCP integration |
| `servers` | list | `[]` | Stable | MCP server configurations |
| `auto_discover` | bool | `True` | Stable | Auto-discover tools on connect |
| `connect_timeout` | float | `30.0` | Stable | Connection timeout |
| `retry_attempts` | int | `3` | Stable | Connection retry attempts |
| `retry_delay` | float | `1.0` | Stable | Delay between retries |
| `tool_risk_overrides` | dict | `{}` | Stable | Override risk levels for MCP tools |

### MCPServerConfig (per-server)

| Field | Type | Default | Stability | Effect |
|---|---|---|---|---|
| `name` | str | *(required)* | Stable | Server identifier |
| `command` | str \| None | None | Stable | stdio command |
| `args` | list | `[]` | Stable | Command arguments |
| `env` | dict | `{}` | Stable | Environment variables |
| `url` | str \| None | None | Stable | SSE/Streamable HTTP URL |
| `transport` | str | `"stdio"` | Stable | `"stdio"` or `"http"` |
| `enabled` | bool | `True` | Stable | Whether to connect |
| `description` | str | `""` | Stable | Human-readable description |

### DashboardConfig

| Field | Type | Default | Env var | Stability | Effect |
|---|---|---|---|---|---|
| `api_key` | str \| None | None | `SHARP_API_KEY` | Stable | API key for auth |
| `auth_required` | bool | `True` | — | Stable | Require auth on `/api/*` |
| `dev_mode` | bool | `False` | — | Stable | Disable all auth/CORS/rate-limit |
| `cors_origins` | list | `["http://localhost:3000", "http://localhost:8080"]` | — | Stable | Allowed browser origins |
| `rate_limit_enabled` | bool | `True` | — | Stable | Enable rate limiting |
| `rate_limit_rpm` | int | `60` | — | Stable | General requests per minute |
| `rate_limit_expensive_rpm` | int | `10` | — | Stable | Expensive endpoint RPM |

## Compatibility rules

- Unknown fields fail Pydantic validation.
- Deprecated fields emit warnings for one minor version, then raise errors.
- Renames require migration notes in CHANGELOG.md.
- Env vars do NOT override explicit Python args.
- YAML `${VAR}` expansion happens at load time, not at access time.
