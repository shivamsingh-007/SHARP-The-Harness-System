# Extending SHARP

How to add tools, validators, providers, hooks, observability, and middleware.

Each extension point follows the same template: what it is, when to use it, minimal example, contract, common mistakes, security note.

---

## 1. Tools

### What it is

Tools let the LLM call external functions during execution. SHARP auto-extracts JSON Schema from your function signature.

### When to use it

When the LLM needs to read files, call APIs, query databases, or run computations.

### Minimal example

```python
from sharp.harness import Harness, HarnessConfig
from sharp.harness.core.types import RiskLevel

config = HarnessConfig.github_models(model="gpt-4o-mini")

async with Harness(config=config) as engine:

    @engine.tool(risk_level=RiskLevel.READ)
    async def get_weather(city: str) -> str:
        """Get current weather for a city.

        Args:
            city: City name (e.g. "London", "New York")
        """
        return f"Weather in {city}: 22C, sunny"

    result = await engine.run("What's the weather in Tokyo?")
    print(result.output)
```

### Contract

- **Function must be async.** Synchronous tools block the event loop.
- **Return type must be `str`.** Non-string returns are stringified.
- **Docstring becomes the tool description** shown to the LLM.
- **Type hints become JSON Schema** (`str`→string, `int`→integer, `float`→number, `bool`→boolean, `list`→array, `dict`→object).
- **Parameters without defaults are required** in the schema.
- **Errors:** raise exceptions; SHARP catches them and returns `ToolResult(success=False, error=...)`.
- **Risk levels:** `READ` (safe), `WRITE` (modifies state), `EXECUTE` (runs commands), `CRITICAL` (destructive). `EXECUTE` and `CRITICAL` require approval by default.

### Common mistakes

- **Do not** make tools synchronous. Use `async def`.
- **Do not** return non-string types without converting. Return `str`.
- **Do not** suppress errors silently. Let exceptions propagate — SHARP handles them.
- **Do not** use `RiskLevel.EXECUTE` without considering approval gates.

### Security note

Tools registered via `@engine.tool()` are subject to path sandboxing, blocked command checks, and approval gates. If you need to bypass these, you are building an internal tool, not an extension.

---

## 2. Validators

### What it is

Validators check LLM output quality before returning results. SHARP has two layers: rule-based (fast, deterministic) and LLM judge (semantic, slower).

### When to use it

When you need to enforce output format, reject hallucinations, or gate quality before downstream use.

### Minimal example

```python
from sharp.harness.core.types import ValidationLevel

config = HarnessConfig()
config.validation.enabled = True
config.validation.level = ValidationLevel.STRICT
config.validation.min_score = 0.7
```

Custom rule:

```python
from sharp.harness.validation.validator import Rule, RuleBasedValidator

validator = RuleBasedValidator()
validator.add_rule(Rule(
    name="no_markdown_headers",
    check=lambda r: not r.startswith("#"),
    message="Response should not start with markdown headers",
    severity="warning",
))
```

### Contract

- **ValidationResult** contains: `passed` (bool), `score` (0.0–1.0), `feedback` (str), `issues` (list), `suggestions` (list).
- **Fail-closed:** on any validation error, `passed=False` and `score=0.0`. The judge does not auto-pass on failure.
- **Score combination:** rule-based and judge scores are averaged; `passed` is ANDed.
- **Retries:** on failure, the engine mutates context and retries up to `max_retries`.

### Common mistakes

- **Do not** override fail-closed behavior. If validation throws an error, the result must fail.
- **Do not** set `min_score=0.0` unless you intentionally want to skip quality checks.
- **Do not** use the LLM judge with local models that cannot produce structured JSON.

### Security note

Validation rules run in-process. Malicious rule functions could execute arbitrary code. Only install rules from trusted sources.

---

## 3. Providers

### What it is

SHARP uses [LiteLLM](https://docs.litellm.ai) as a universal adapter. Any provider supported by LiteLLM works out of the box.

### When to use it

When you want to switch LLM providers or use a custom API endpoint.

### Minimal example

```python
from sharp.harness import HarnessConfig

# OpenAI
config = HarnessConfig()
config.llm.provider = "openai"
config.llm.model = "gpt-4o"
config.llm.api_key = "sk-..."

# Anthropic
config = HarnessConfig()
config.llm.provider = "anthropic"
config.llm.model = "claude-3-5-sonnet-20241022"
config.llm.api_key = "sk-ant-..."

# Ollama (local, no key needed)
config = HarnessConfig.ollama(model="llama3.1:8b")

# GitHub Models
config = HarnessConfig.github_models(model="gpt-4o-mini")
```

### Contract

- **Model format:** `"provider/model"` or full LiteLLM model ID.
- **Token counting:** built-in for known models (gpt-4o, gpt-4o-mini, claude-3-5-sonnet, etc.). Unknown models return `cost_usd=0.0`.
- **Timeout:** controlled by `LLMConfig.timeout`. Default 60s.
- **Errors:** provider errors raise `ProviderError(provider, message)`.

### Common mistakes

- **Do not** bypass LiteLLM unless you handle token counting and cost tracking yourself.
- **Do not** set `api_key` in code for production use. Use env vars.
- **Do not** use the same model for execution and judging. Local models cannot be judges.

### Security note

API keys are stored in `LLMConfig`. Do not log them. The `api_key` field is excluded from dashboard config responses.

---

## 4. Hooks

### What it is

Hooks are async callbacks fired at lifecycle points. They can read/write shared state and cancel actions.

### When to use it

When you need logging, metrics, pre-flight checks, or custom behavior at specific pipeline stages.

### Minimal example

```python
from sharp.harness.execution.hooks import HookEvent, HookContext

async def log_start(ctx: HookContext):
    print(f"Starting: {ctx.data['user_request']}")

async def log_end(ctx: HookContext):
    print(f"Done: success={ctx.data['success']}")

engine.hooks.register(HookEvent.SESSION_START, log_start)
engine.hooks.register(HookEvent.SESSION_END, log_end)
```

### Contract

- **6 lifecycle events:** `SESSION_START`, `SESSION_END`, `BEFORE_EXECUTE`, `AFTER_EXECUTE`, `ON_VALIDATION_FAILURE`, `ON_RETRY`.
- **Handler signature:** `async def handler(ctx: HookContext) -> None`
- **Cancellation:** set `ctx.cancel = True` to skip the current action.
- **Data keys by event:**
  - `SESSION_START`: `user_request`, `trace_id`
  - `SESSION_END`: `trace_id`, `output`, `success`, `attempts`
  - `BEFORE_EXECUTE`: `attempt`, `user_request`
  - `AFTER_EXECUTE`: `attempt`, `output`, `validation_score`
  - `ON_VALIDATION_FAILURE`: `attempt`, `issues`, `score`, `output`
  - `ON_RETRY`: `attempt`, `validation_result`
- **Order:** hooks fire in registration order. Iteration stops early if `cancel` is set.

### Common mistakes

- **Do not** block in hooks. They are async; use `await` for I/O.
- **Do not** modify `ctx.data` unless you understand the downstream effects.
- **Do not** register the same handler twice for the same event.

### Security note

Hooks have full access to request data. Do not log secrets. Hooks run in-process and can execute arbitrary code.

---

## 5. Observability

### What it is

Structured logging, tracing, metrics, and telemetry for debugging and monitoring.

### When to use it

When you need to debug pipeline issues, track performance, or export data to observability platforms.

### Minimal example

```python
from sharp.harness import HarnessConfig

config = HarnessConfig()
config.observability.metrics_enabled = True
config.observability.tracing_enabled = True
config.observability.log_file = "harness.log"
```

Custom span:

```python
from sharp.harness.observability.tracing import SpanTracker

tracker = SpanTracker()
with tracker.span("my_operation", trace_id="abc-123") as span:
    # ... do work ...
    pass

spans = tracker.get_spans_for_trace("abc-123")
```

### Contract

- **MetricsCollector:** in-memory trace metrics with `start_trace()` / `end_trace()`.
- **SpanTracker:** in-memory span recording with parent-child hierarchy.
- **TelemetryCollector:** append-only JSON-lines log with in-memory buffer.
- **Reserved fields:** `request_id`, `session_id`, `tool_name`, `provider`, `latency_ms`. Do not override these.
- **Error classification:** `ErrorClass` enum (`PROVIDER`, `TOOL`, `VALIDATION`, `TIMEOUT`, `AUTH`, `CONFIG`, `UNKNOWN`).

### Common mistakes

- **Do not** log secrets in structured fields.
- **Do not** enable OTLP export without configuring an endpoint.
- **Do not** rely on `SpanTracker` for production tracing. Use OpenTelemetry for distributed systems.

### Security note

Log files may contain request/response data. Restrict file permissions. Do not ship logs to external services without redacting sensitive content.

---

## 6. HTTP Middleware

### What it is

The FastAPI dashboard has auth, rate limiting, and CORS middleware. You can add custom middleware.

### When to use it

When you need custom authentication, logging, or request transformation for the HTTP API.

### Minimal example

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class CustomHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "X-Custom-Header" not in request.headers:
            return JSONResponse({"detail": "Missing header"}, status_code=400)
        return await call_next(request)

# In create_app():
app.add_middleware(CustomHeaderMiddleware)
```

### Contract

- **Middleware stack order:** CORS → Auth → Rate Limit → Custom.
- **Auth middleware** checks `X-API-Key` on `/api/*` routes. Skipped if `dev_mode=True`.
- **Rate limit middleware** uses per-IP token bucket. Returns 429 with `Retry-After`.
- **Request-scoped:** each request gets its own scope. Do not store request data in module-level variables.

### Common mistakes

- **Do not** remove rate limiting. It protects against abuse.
- **Do not** store request-scoped data in global state.
- **Do not** add middleware that blocks health checks (`/api/health`).

### Security note

Middleware runs on every request. Keep it fast. Do not perform blocking I/O in middleware. Use `async` for all operations.
