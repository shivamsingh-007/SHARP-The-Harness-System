<div align="center">

# SHARP

**S**ystem for **H**arnessing **A**ugmented **R**easoning and **T**ransforming **H**euristics

A modular orchestration framework for LLM tools and agents with context engineering, prompt engineering, validation, and MCP integration.

**Not production-ready.** See [PRODUCT_CONTRACT.md](PRODUCT_CONTRACT.md) for guarantees and limits.

</div>

## Install

```bash
pip install -e .
```

Python 3.11+. For development: `pip install -e ".[dev]"`

## Quickstart

```bash
export GITHUB_TOKEN=your_token_here
python examples/minimal.py
```

Or write it inline:

```python
import asyncio
from sharp.harness import Harness, HarnessConfig

async def main():
    config = HarnessConfig.github_models(model="gpt-4o-mini")
    async with Harness(config=config) as engine:
        result = await engine.run("Summarize why rate limiting matters in one paragraph.")
        print(result.output)
        print(f"\nTokens: {result.total_tokens} | Cost: ${result.total_cost_usd:.4f}")

asyncio.run(main())
```

Expected output:

```
Rate limiting matters because it protects services from overload,
abuse, and noisy-neighbor traffic...

Tokens: 42 | Cost: $0.0001
```

## Where to go next

- **[Quickstart](docs/QUICKSTART.md)** — full install-to-first-run path
- **[Canonical Examples](docs/CANONICAL_EXAMPLES.md)** — scripted use + HTTP API service
- **[Config Contract](docs/CONFIG_CONTRACT.md)** — all fields, defaults, stability
- **[Extending SHARP](docs/EXTENDING.md)** — tools, validators, hooks, providers, middleware
- **[Limitations](docs/LIMITATIONS.md)** — what SHARP is not

## Public API

```python
from sharp.harness import Harness, HarnessConfig, HarnessResult, ValidationResult, HarnessError
```

| Symbol | What it is |
|---|---|
| `Harness` | The engine — runs the full pipeline |
| `HarnessConfig` | Configuration (use `.github_models()`, `.ollama()`, or `.from_yaml()`) |
| `HarnessResult` | Return type of `engine.run()` — stable fields across v0.x |
| `ValidationResult` | Validation output — `passed`, `score`, `feedback`, `issues` |
| `HarnessError` | Base error type for all SHARP exceptions |

Everything else is internal unless documented in [EXTENDING.md](docs/EXTENDING.md).

---

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00FF00?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Version: 0.2.0](https://img.shields.io/badge/Version-0.2%20Dev%20Preview-FF6B35?style=for-the-badge)](#testing)
[![Tests: 603/603](https://img.shields.io/badge/Tests-603%20passed-44CC11?style=for-the-badge&logo=pytest&logoColor=white)](#testing)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-FF6B35?style=for-the-badge&logo=modelcontextprotocol&logoColor=white)](#architecture)

---

## Architecture

SHARP runs a 5-stage pipeline: **Context → Prompt → Execute → Validate → Respond**, with safety (circuit breaker, budget, approval gates) and retry woven throughout.

15 modules: core, orchestration, execution, mcp, agents, dashboard, context, validation, prompt, safety, artifacts, observability, state, benchmarks, utils. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full map.

## Testing

```bash
# Mocked tests (no LLM required)
pytest tests/ -m "not llm_integration" -q

# LLM integration tests (requires GITHUB_TOKEN)
pytest tests/test_llm_integration.py -v -m llm_integration
```

603 unit tests verify plumbing and control flow. 10 integration tests verify real LLM output shape. CI runs mocked tests by default.

## License

MIT
