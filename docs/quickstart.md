# Quickstart

Run SHARP with one model and one tool loop in under 5 minutes.

## Who this is for

Use this if you want to run SHARP with one model and one tool loop.

Do not start here if you need dashboard, MCP, or custom validators.

## Install

```bash
git clone https://github.com/shivamsingh-007/SHARP-The-Harness-System.git
cd SHARP-The-Harness-System
pip install -e .
```

Python 3.11+ required. For development:

```bash
pip install -e ".[dev]"
```

## Set one provider

SHARP uses GitHub Models API by default. Set one env var:

```bash
export GITHUB_TOKEN=your_token_here
```

## Run the minimal script

```bash
python examples/minimal.py
```

Or write it inline:

```python
import asyncio
from sharp.harness import Harness, HarnessConfig

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:
        result = await engine.run(
            "Summarize why rate limiting matters in one paragraph."
        )
        print(result.output)
        print(f"\nTokens: {result.total_tokens} | Cost: ${result.total_cost_usd:.4f}")

asyncio.run(main())
```

## Expected output

```
Rate limiting matters because it protects services from overload,
abuse, and noisy-neighbor traffic...

Tokens: 42 | Cost: $0.0001
```

## Common failure

**`ValueError: No GitHub token found`** — set the env var:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

## Next paths

- **Want YAML config?** → [CONFIG_CONTRACT.md](CONFIG_CONTRACT.md)
- **Want the HTTP API?** → [CANONICAL_EXAMPLES.md](CANONICAL_EXAMPLES.md) (Example 2)
- **Want MCP?** → [EXTENDING.md](EXTENDING.md)
- **Want custom tools?** → [EXTENDING.md](EXTENDING.md)
- **Want local models (Ollama)?** → `HarnessConfig.ollama(model="llama3.1:8b")`
