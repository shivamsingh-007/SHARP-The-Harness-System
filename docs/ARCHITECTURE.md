# Architecture

One page to orient yourself after the quickstart.

## Runtime flow

```
engine.run(user_request)
  1. Pre-flight    Circuit breaker OK? Budget OK?
  2. Context        Curate sources: user, memory, docs, prior outputs
  3. Prompt         System prompt + tools + memory → augmented prompt
  4. Execute        ReAct loop (tool calling) or direct LLM call
  5. Validate       Rule-based + optional LLM judge
  6. Retry          On failure: mutate context, re-run (max N attempts)
  7. Post-flight    Record metrics, update circuit breaker, save checkpoint
```

## State boundaries

| Scope | What lives here |
|---|---|
| **Request-scoped** | `trace_id`, loop state, validation results, tool call history |
| **Process-scoped** | Metrics collector, circuit breaker state, budget counters, MCP connections |
| **Persistent** | Checkpoints, sessions, audit logs (file or Redis) |

## Key modules

| Module | Purpose | Public? |
|---|---|---|
| `core/engine.py` | Pipeline orchestrator | Yes (`Harness`) |
| `core/config.py` | Configuration models | Yes (`HarnessConfig`) |
| `core/types.py` | Shared types and enums | Yes (`HarnessResult`, etc.) |
| `execution/loop.py` | ReAct execution loop | Internal |
| `execution/providers.py` | LiteLLM provider wrapper | Internal |
| `execution/tools.py` | Tool registry and governance | Internal |
| `execution/hooks.py` | Lifecycle hook system | Yes (via `engine.hooks`) |
| `execution/subagents.py` | Sub-agent spawning | Internal |
| `context/curator.py` | Context source curation | Internal |
| `prompt/composer.py` | Augmented prompt assembly | Internal |
| `validation/validator.py` | Combined validation pipeline | Internal |
| `validation/judge.py` | LLM-as-judge evaluation | Internal |
| `validation/rules.py` | Rule-based validation | Internal |
| `mcp/bridge.py` | MCP ↔ SHARP tool bridge | Internal |
| `mcp/client.py` | MCP server connections | Internal |
| `orchestration/orchestrator.py` | Multi-interface routing | Yes (`Orchestrator`) |
| `agents/coding.py` | DPEVR coding agent | Internal |
| `dashboard/server.py` | FastAPI HTTP + WebSocket | Internal |
| `observability/metrics.py` | Trace metrics collection | Internal |
| `safety/circuit_breaker.py` | Failure detection + recovery | Internal |
| `safety/budget.py` | Token/cost budget enforcement | Internal |
| `state/checkpoint.py` | Checkpoint persistence | Internal |
| `benchmarks/harness_bench.py` | Benchmark runner | Internal |
| `artifacts/manager.py` | Feature/progress tracking | Internal |

## Extension points

Six ways to extend SHARP without modifying internals:

1. **Tools** — `@engine.tool()` decorator ([EXTENDING.md](EXTENDING.md#1-tools))
2. **Validators** — rule-based or LLM judge ([EXTENDING.md](EXTENDING.md#2-validators))
3. **Providers** — any LiteLLM-supported provider ([EXTENDING.md](EXTENDING.md#3-providers))
4. **Hooks** — 6 lifecycle events ([EXTENDING.md](EXTENDING.md#4-hooks))
5. **Observability** — metrics, tracing, telemetry ([EXTENDING.md](EXTENDING.md#5-observability))
6. **HTTP middleware** — auth, rate limiting, custom ([EXTENDING.md](EXTENDING.md#6-http-middleware))

## What to ignore

90% of the codebase is internal plumbing. If you are a user, you need:
- `Harness` + `HarnessConfig` (start here)
- `engine.run()` + `HarnessResult` (core loop)
- `@engine.tool()` (if using tools)

If you are an extender, see [EXTENDING.md](EXTENDING.md). If you need the config schema, see [CONFIG_CONTRACT.md](CONFIG_CONTRACT.md).
