# Canonical Examples

Two blessed integration patterns. Start here; everything else is advanced.

## Example 1: Single-engine scripted use

Best for: local scripts, CLI tools, simple app integration.

When NOT to use: multi-request services, team-shared deployments (use Example 2).

```python
import asyncio
from sharp.harness import Harness, HarnessConfig
from sharp.harness.core.types import RiskLevel

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")

    async with Harness(config=config) as engine:

        # --- 1. Register a custom tool ---
        @engine.tool(risk_level=RiskLevel.READ)
        async def get_weather(city: str) -> str:
            """Get current weather for a city."""
            return f"Weather in {city}: 22C, sunny"

        # --- 2. Run with the tool ---
        result = await engine.run(
            "What's the weather in Tokyo? Also convert 100 USD to EUR."
        )
        print(result.output)

        # --- 3. Inspect result fields ---
        print(f"Success: {result.success}")
        print(f"Tokens:  {result.total_tokens}")
        print(f"Cost:    ${result.total_cost_usd:.4f}")
        print(f"Latency: {result.total_latency_ms:.0f}ms")
        print(f"Score:   {result.validation_score}")

        # --- 4. Optional: add context for multi-turn ---
        engine.add_memory("user_style", "User prefers concise responses")
        r2 = await engine.run("What did I just ask about?")
        print(r2.output)

asyncio.run(main())
```

**What this shows:**

| Step | What happens |
|---|---|
| Config | GitHub Models API, single env var (`GITHUB_TOKEN`) |
| Tool registration | `@engine.tool()` decorator, auto-extracts schema from type hints |
| run() | Full pipeline: context → prompt → execute → validate → result |
| Result | Stable shape: `success`, `output`, `total_tokens`, `total_cost_usd`, etc. |
| Memory | `add_memory()` persists across calls within the same engine instance |

---

## Example 2: HTTP API service

Best for: teams embedding SHARP behind an internal service, multi-request orchestration.

When NOT to use: single-user scripts (use Example 1 instead).

### Start the service

```python
# api_service.py
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sharp.harness import Harness, HarnessConfig

app = FastAPI()
config = HarnessConfig.github_models(model="gpt-4o-mini")

import os
API_KEY = os.environ.get("SHARP_API_KEY", "")

class RunRequest(BaseModel):
    prompt: str

@app.post("/api/engine/run")
async def run_engine(req: RunRequest, x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
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
export SHARP_API_KEY=my_secret_key
export GITHUB_TOKEN=ghp_your_token_here
python api_service.py
```

### Call the API

```bash
# Success
curl -X POST http://localhost:8000/api/engine/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my_secret_key" \
  -d '{"prompt": "Summarize rate limiting in one sentence"}'

# Response:
# {"success":true,"output":"Rate limiting...","total_tokens":38,"total_cost_usd":0.0001}

# Auth failure
curl -X POST http://localhost:8000/api/engine/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: wrong_key" \
  -d '{"prompt": "Hello"}'

# Response:
# {"detail":"Invalid API key"}
```

### Response shape

```json
{
  "success": true,
  "output": "Rate limiting protects services from overload...",
  "total_tokens": 38,
  "total_cost_usd": 0.0001
}
```

**What this shows:**

| Step | What happens |
|---|---|
| Auth | `X-API-Key` header checked against `SHARP_API_KEY` env var |
| Engine reuse | Config created once, engine created per request (stateless) |
| Error handling | 401 on bad key, 429 on rate limit (built into middleware) |
| Response | Same `HarnessResult` fields as Example 1, serialized to JSON |
