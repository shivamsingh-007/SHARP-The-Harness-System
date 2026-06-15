# Examples

Common SHARP usage patterns with working code.

## Basic query

```python
import asyncio
from sharp import HarnessEngine, HarnessConfig

async def main():
    engine = HarnessEngine(HarnessConfig.ollama())
    result = await engine.run("What is the capital of France?")
    print(result.output)
    # → "The capital of France is Paris."

asyncio.run(main())
```

## With documents

```python
async def summarize_codebase():
    engine = HarnessEngine(HarnessConfig.ollama())

    readme = open("README.md").read()
    changelog = open("CHANGELOG.md").read()

    result = await engine.run(
        "Summarize this project in 3 sentences",
        docs=[
            {"name": "readme", "content": readme},
            {"name": "changelog", "content": changelog},
        ],
    )
    print(result.output)
```

## Custom tools

```python
async def with_custom_tools():
    from sharp.harness.core.types import RiskLevel

    engine = HarnessEngine(HarnessConfig.ollama())

    @engine.tool(risk_level=RiskLevel.READ)
    async def get_weather(city: str) -> str:
        """Get current weather for a city.

        Args:
            city: City name (e.g., "London", "New York")
        """
        # Replace with real API call
        return f"Weather in {city}: 22°C, sunny"

    @engine.tool(risk_level=RiskLevel.READ)
    async def convert_currency(amount: float, from_curr: str, to_curr: str) -> str:
        """Convert currency amounts.

        Args:
            amount: Amount to convert
            from_curr: Source currency code (e.g., "USD")
            to_curr: Target currency code (e.g., "EUR")
        """
        # Replace with real API call
        rates = {"USD_EUR": 0.85, "EUR_USD": 1.18}
        rate = rates.get(f"{from_curr}_{to_curr}", 1.0)
        result = amount * rate
        return f"{amount} {from_curr} = {result:.2f} {to_curr}"

    result = await engine.run("What's the weather in Tokyo? Also convert 100 USD to EUR.")
    print(result.output)
```

## Memory and context

```python
async def conversational():
    engine = HarnessEngine(HarnessConfig.ollama())

    # Add persistent memory
    engine.add_memory("user_name", "Alice")
    engine.add_memory("preferences", "User prefers short, direct answers")

    # First turn
    r1 = await engine.run("What's my name?")
    print(r1.output)  # → "Your name is Alice."

    # Second turn — engine remembers prior output
    r2 = await engine.run("And what do I prefer?")
    print(r2.output)  # → "You prefer short, direct answers."
```

## Multi-turn conversation

```python
async def multi_turn():
    engine = HarnessEngine(HarnessConfig.ollama())

    r1 = await engine.run("What is 5 + 3?")
    print(r1.output)  # → "8"

    r2 = await engine.run("Now multiply that by 2")
    print(r2.output)  # → "16"
```

## YAML config

Create `harness.yaml`:

```yaml
llm:
  provider: openai
  model: gpt-4o
  temperature: 0.7
  max_tokens: 2048

validation:
  enabled: true
  max_retries: 3
  min_score: 0.7

safety:
  circuit_breaker_enabled: true
  failure_threshold: 5
  max_cost_usd: 10.0
  max_tokens: 100000
```

Then use it:

```python
config = HarnessConfig.from_yaml("harness.yaml")
engine = HarnessEngine(config)
result = await engine.run("Explain async/await in Python")
```

## Hooks

```python
async def with_hooks():
    from sharp.harness.execution.hooks import HookEvent, HookContext

    engine = HarnessEngine(HarnessConfig.ollama())

    async def log_start(ctx: HookContext):
        print(f"[HOOK] Starting: {ctx.data['user_request']}")

    async def log_end(ctx: HookContext):
        print(f"[HOOK] Done: success={ctx.data['success']}")

    engine.hooks.register(HookEvent.SESSION_START, log_start)
    engine.hooks.register(HookEvent.SESSION_END, log_end)

    result = await engine.run("Hello")
```

## MCP integration

```python
async def with_mcp():
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
        result = await engine.run("List all Python files in this project")
        print(result.output)
```

## Orchestrator (multi-interface routing)

```python
async def orchestrator_example():
    from sharp import Orchestrator, OrchestratorConfig, HarnessConfig

    config = HarnessConfig.ollama()
    orch_config = OrchestratorConfig(engine_config=config)
    orchestrator = Orchestrator(config=orch_config)

    result = await orchestrator.handle_request(
        raw_request={"message": "Fix the bug in login.py"},
        interface_type="claude_code",
    )
    print(result.output)
    print(f"Routed to: {result.audit_entry.interface_type}")
```

## CLI usage

```bash
# Basic query
sharp run "What is Python?"

# With config
sharp run "Explain decorators" --config harness.yaml

# Override model
sharp run "List files" --model gpt-4o-mini

# Verbose output
sharp run "Debug this function" --verbose

# Health check
sharp health

# Show current config
sharp config-show
```

## Error handling

```python
async def safe_run():
    from sharp.harness.core.errors import (
        CircuitBreakerOpenError,
        BudgetExceededError,
        RetryExhaustedError,
    )

    engine = HarnessEngine(HarnessConfig.ollama())

    try:
        result = await engine.run("Complex task")
        if result.success:
            print(result.output)
        else:
            print(f"Failed: {result.error}")
    except CircuitBreakerOpenError:
        print("Too many failures — try again later")
    except BudgetExceededError:
        print("Budget exhausted")
    except RetryExhaustedError:
        print("Could not produce valid output after retries")
```

## Streaming (not yet implemented)

Streaming support is planned. For now, use the async `run()` method and display the result when complete.
