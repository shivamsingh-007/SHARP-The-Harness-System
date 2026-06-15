# Engine

`HarnessEngine` is the core orchestrator. It runs the full pipeline: context curation, prompt composition, LLM execution, validation, and retry.

## Creating an engine

```python
from sharp import HarnessEngine, HarnessConfig

# Default config (OpenAI gpt-4o)
engine = HarnessEngine()

# Local Ollama
engine = HarnessEngine(HarnessConfig.ollama())

# From YAML file
config = HarnessConfig.from_yaml("harness.yaml")
engine = HarnessEngine(config)
```

## Running requests

```python
result = await engine.run("What is the capital of France?")
```

The `run()` method returns a `HarnessResult`:

```python
result.success        # bool — did it succeed?
result.output         # str — the LLM's response
result.total_tokens   # int — tokens consumed
result.total_cost_usd # float — estimated cost
result.total_latency_ms # float — wall clock time
result.validation_score # float — 0.0 to 1.0
result.attempts       # int — how many tries (1 = first pass)
result.trace_id       # str — unique ID for this run
result.error          # str | None — error message if failed
```

## How run() works

Each call to `run()` executes these phases:

```
1. Pre-flight checks    Circuit breaker OK? Budget OK?
         |
2. Context Engineering   Curate sources: user request, memory, docs, prior outputs
         |
3. Prompt Engineering    Compose system prompt + user message + tool definitions
         |
4. Execution             LLM call — either direct or through ReAct loop
         |
5. Validation            Rule-based + optional LLM judge
         |
6. Retry                 If validation fails, mutate context and re-run
         |
7. Post-flight           Record metrics, update circuit breaker, save checkpoint
```

## Chat mode vs Agent mode

SHARP has two execution paths, chosen automatically:

### Chat mode (simple prompts)

Short prompts without tool-use keywords get a direct LLM call — no ReAct loop, no tool definitions injected.

```python
result = await engine.run("What is Python?")
# → Direct LLM call, fast path (~5s with Ollama)
```

Triggers when: prompt < 60 chars AND doesn't contain keywords like "file", "list", "calculate", "search", etc.

### Agent mode (tool-calling prompts)

Prompts that need tools go through the ReAct loop: Thought → Action → Observation → Final Answer.

```python
result = await engine.run("List the files in the current directory")
# → ReAct loop: model calls list_directory tool, observes output, produces answer
```

The model can call tools multiple times before giving a final answer. The loop handles:
- Native OpenAI function calling (when the LLM supports it)
- Text-based ReAct format (fallback for models that don't)
- Repeated tool call detection (stops the model from looping)
- Forced final answer after max iterations

## Adding context

### Memory

```python
engine.add_memory("user_style", "User prefers concise responses")
engine.load_memory_file("CLAUDE.md")
```

Memory is injected into every prompt's context.

### Documents

```python
result = await engine.run(
    "Summarize this codebase",
    docs=[
        {"name": "readme", "content": open("README.md").read()},
        {"name": "changelog", "content": open("CHANGELOG.md").read()},
    ],
)
```

### Prior outputs

The engine automatically feeds previous outputs into context for multi-turn conversations:

```python
r1 = await engine.run("What is 5+3?")   # gets 8
r2 = await engine.run("Now multiply by 2")  # engine knows r1's output
```

## Hooks

Register callbacks for lifecycle events:

```python
from sharp.harness.execution.hooks import HookEvent, HookContext

async def on_start(ctx: HookContext):
    print(f"Starting run: {ctx.data['user_request']}")

engine.hooks.register(HookEvent.SESSION_START, on_start)
```

Available events: `SESSION_START`, `SESSION_END`, `BEFORE_EXECUTE`, `AFTER_EXECUTE`, `BEFORE_VALIDATION`, `AFTER_VALIDATION`, `ON_RETRY`, `ON_SUCCESS`, `ON_FAILURE`, `ON_TOOL_CALL`.

## MCP servers

Connect to MCP servers for additional tools:

```python
from sharp import HarnessEngine, HarnessConfig

config = HarnessConfig()
config.mcp.servers = [
    {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
        "transport": "stdio",
    },
]

async with HarnessEngine(config) as engine:
    # MCP tools auto-discovered and registered
    result = await engine.run("List all Python files")
```

## Safety

```python
config = HarnessConfig()
config.safety.circuit_breaker_enabled = True
config.safety.failure_threshold = 5       # open after 5 failures
config.safety.max_cost_usd = 10.0         # hard cost limit
config.safety.max_tokens = 100000         # hard token limit
```

The circuit breaker opens after N consecutive failures and auto-recovers after a cooldown. Budget limits are enforced per engine instance.

## Error handling

```python
from sharp.harness.core.errors import (
    CircuitBreakerOpenError,
    BudgetExceededError,
    RetryExhaustedError,
)

try:
    result = await engine.run("...")
except CircuitBreakerOpenError:
    print("Too many failures, circuit breaker open")
except BudgetExceededError:
    print("Cost or token budget exceeded")
except RetryExhaustedError:
    print("Validation failed after all retries")
```

## Cleanup

```python
# If using MCP, close connections when done
await engine.close()

# Or use as context manager
async with HarnessEngine(config) as engine:
    result = await engine.run("...")
# connections auto-closed
```
