# Examples

Working code you can copy and run.

## Minimal — one prompt, one result

```python
import asyncio
from sharp.harness import Harness, HarnessConfig

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:
        result = await engine.run("What is the capital of France?")
        print(result.output)

asyncio.run(main())
```

## With tools — let the model call functions

```python
import asyncio
from sharp.harness import Harness, HarnessConfig
from sharp.harness.core.types import RiskLevel

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:

        @engine.tool(risk_level=RiskLevel.READ)
        async def get_weather(city: str) -> str:
            """Get current weather for a city."""
            return f"Weather in {city}: 22C, sunny"

        result = await engine.run("What's the weather in Tokyo?")
        print(result.output)
        print(f"Tools used: {result.total_tokens} tokens")

asyncio.run(main())
```

## With context — documents and memory

```python
import asyncio
from sharp.harness import Harness, HarnessConfig

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:
        engine.add_memory("user_style", "User prefers concise answers")

        readme = open("README.md").read()
        result = await engine.run(
            "Summarize this project in 3 sentences",
            docs=[{"name": "readme", "content": readme}],
        )
        print(result.output)

asyncio.run(main())
```

## HTTP API — embed behind a service

```python
import os
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sharp.harness import Harness, HarnessConfig

app = FastAPI()
API_KEY = os.environ.get("SHARP_API_KEY", "")

class RunRequest(BaseModel):
    prompt: str

@app.post("/api/engine/run")
async def run_engine(req: RunRequest, x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:
        result = await engine.run(req.prompt)

    return {
        "success": result.success,
        "output": result.output,
        "total_tokens": result.total_tokens,
        "total_cost_usd": result.total_cost_usd,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

```bash
export SHARP_API_KEY=your_secret
export GITHUB_TOKEN=ghp_your_token
python api_service.py
```

```bash
curl -X POST http://localhost:8000/api/engine/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret" \
  -d '{"prompt": "Summarize rate limiting in one sentence"}'
```

## Error handling

```python
import asyncio
from sharp.harness import Harness, HarnessConfig
from sharp.harness.core.errors import (
    CircuitBreakerOpenError,
    BudgetExceededError,
    RetryExhaustedError,
)

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:
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

asyncio.run(main())
```

## YAML config

Create `harness.yaml`:

```yaml
llm:
  model: gpt-4o
  temperature: 0.5

validation:
  max_retries: 3
  min_score: 0.7
```

```python
import asyncio
from sharp.harness import Harness, HarnessConfig

async def main():
    config = HarnessConfig.from_yaml("harness.yaml")
    async with Harness(config=config) as engine:
        result = await engine.run("Explain async/await in Python")
        print(result.output)

asyncio.run(main())
```

## Result fields

`engine.run()` returns a `HarnessResult`:

| Field | Type | Description |
|---|---|---|
| `success` | bool | Whether the pipeline completed |
| `output` | str | The final text output |
| `total_tokens` | int | Tokens consumed |
| `total_cost_usd` | float | Estimated cost |
| `total_latency_ms` | float | Wall-clock time |
| `validation_score` | float | Quality score (0.0–1.0) |
| `attempts` | int | Number of tries (1 = no retries) |
| `trace_id` | str | Unique execution ID |
| `error` | str \| None | Error message if failed |

## More examples

- [examples/minimal.py](examples/minimal.py) — runnable minimal script
- [docs/QUICKSTART.md](docs/QUICKSTART.md) — install to first run
- [docs/EXTENDING.md](docs/EXTENDING.md) — tools, hooks, validators
