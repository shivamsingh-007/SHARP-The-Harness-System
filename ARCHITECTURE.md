# Architecture

How SHARP works under the hood.

## Pipeline overview

```
User Request
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Context    │────▶│   Prompt    │────▶│   Execute   │
│   Curation   │     │  Composer   │     │  ReAct Loop │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌─────────────┐     ┌──────▼──────┐
                    │   Respond   │◀────│   Validate  │
                    │             │     │ Rules+Judge │
                    └─────────────┘     └──────┬──────┘
                                               │
                                        ┌──────▼──────┐
                                        │    Retry    │
                                        │  (on fail)  │
                                        └─────────────┘
```

## Request flow

1. **Pre-flight** — check circuit breaker and budget
2. **Context** — curate sources: user input, memory, documents, prior outputs
3. **Prompt** — assemble system prompt + tools + memory into augmented prompt
4. **Execute** — run LLM via ReAct loop (tool calling) or direct call
5. **Validate** — rule-based checks + optional LLM judge
6. **Retry** — on failure, mutate context with error feedback and re-run
7. **Post-flight** — record metrics, update circuit breaker, save checkpoint

## Core modules

```
sharp/harness/
├── core/              Engine, config, types, errors
├── context/           Context curation, memory, retrieval
├── prompt/            Prompt composition, templates
├── execution/         LLM providers, tool registry, ReAct loop
├── validation/        Rule engine, LLM judge, retry
├── safety/            Circuit breaker, budget, approval gates
├── state/             Checkpoints, sessions, persistence
├── observability/     Metrics, tracing, logging
├── mcp/               MCP client, tool bridge
├── orchestration/     Multi-interface routing
├── agents/            Coding agent, initializer
├── dashboard/         FastAPI HTTP server
├── artifacts/         Feature tracking
├── benchmarks/        Performance harness
└── utils/             Token counting, async helpers
```

## Key components

| Component | Location | Purpose |
|---|---|---|
| `HarnessEngine` | `core/engine.py` | Pipeline orchestrator — runs everything |
| `HarnessConfig` | `core/config.py` | Configuration with factory methods |
| `ExecutionLoop` | `execution/loop.py` | ReAct loop with tool calling |
| `ToolRegistry` | `execution/tools.py` | Tool governance and risk classification |
| `ResponseValidator` | `validation/validator.py` | Combined rule + judge validation |
| `HookRegistry` | `execution/hooks.py` | 6 lifecycle events |
| `CircuitBreaker` | `safety/circuit_breaker.py` | Failure detection and recovery |
| `MCPClient` | `mcp/client.py` | MCP server connections |

## Extension points

Six ways to extend SHARP without modifying internals:

1. **Tools** — `@engine.tool()` decorator with risk classification
2. **Validators** — rule-based or LLM judge
3. **Providers** — any LiteLLM-supported provider
4. **Hooks** — `SESSION_START`, `SESSION_END`, `BEFORE_EXECUTE`, `AFTER_EXECUTE`, `ON_VALIDATION_FAILURE`, `ON_RETRY`
5. **Observability** — metrics, tracing, structured logging
6. **HTTP middleware** — auth, rate limiting, custom

See [docs/EXTENDING.md](docs/EXTENDING.md) for details.

## State boundaries

| Scope | What lives here |
|---|---|
| **Request** | trace_id, loop state, validation results, tool calls |
| **Process** | metrics, circuit breaker, budget counters, MCP connections |
| **Persistent** | checkpoints, sessions, audit logs (file or Redis) |

## What to ignore

90% of the codebase is internal plumbing. If you're a user, you need:
- `Harness` + `HarnessConfig` — start here
- `engine.run()` + `HarnessResult` — core loop
- `@engine.tool()` — if using tools

Everything else is internal unless documented in [docs/EXTENDING.md](docs/EXTENDING.md).
