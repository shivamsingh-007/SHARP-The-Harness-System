<div align="center">

<img src="assets/sharp-banner.svg" alt="SHARP — System for Harnessing Augmented Reasoning" width="100%" />

**A modular orchestration framework for LLM tools and agents.**

Context engineering, prompt composition, tool execution, validation, and retry — orchestrated as a single pipeline.

*Not production-ready. Honest about what it is and isn't.*

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00FF00?style=flat-square)](https://opensource.org/licenses/MIT)
[![Tests: 603](https://img.shields.io/badge/Tests-603%20passed-44CC11?style=flat-square&logo=pytest&logoColor=white)](#testing)
[![Version: 0.2.1](https://img.shields.io/badge/Version-0.2.1-FF6B35?style=flat-square)](#status)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-FF6B35?style=flat-square&logo=modelcontextprotocol&logoColor=white)](#what-sharp-is-not)

</div>

---

## What SHARP is

SHARP runs a structured pipeline: **Context → Prompt → Execute → Validate → Respond**. It handles tool execution via a ReAct loop, validates output with rules and an optional LLM judge, and retries with feedback when quality is low.

```python
from sharp.harness import Harness, HarnessConfig

config = HarnessConfig.github_models(model="gpt-4o-mini")

async with Harness(config=config) as engine:
    result = await engine.run("Summarize why rate limiting matters.")
    print(result.output)
```

## Why it exists

Most LLM agent frameworks give you a prompt and hope for the best. SHARP treats the **entire pipeline** as an engineered system — curating context, composing prompts, executing with tools, validating responses, and retrying with feedback.

Built for developers who need a reliable orchestration layer they can inspect, extend, and trust.

## Features

- **ReAct execution loop** — tool calling with native OpenAI function calling and text-based fallback
- **Dual validation** — rule-based checks + LLM-as-judge with fail-closed behavior
- **Context engineering** — multi-source curation with memory, docs, and prior outputs
- **Tool governance** — risk classification (READ → WRITE → EXECUTE → CRITICAL) with approval gates
- **MCP integration** — connect to any Model Context Protocol server for additional tools
- **Safety layer** — circuit breaker, budget limits, and human-in-the-loop approval
- **Retry engine** — mutates context with error feedback and re-runs on validation failure
- **Hook system** — 6 lifecycle events for logging, metrics, and custom behavior
- **HTTP API** — FastAPI service with auth, rate limiting, and CORS
- **Multi-provider** — OpenAI, Anthropic, Ollama, and more via LiteLLM

## Quickstart

```bash
pip install -e .
export GITHUB_TOKEN=your_token_here
python examples/minimal.py
```

That's it. See [SETUP.md](SETUP.md) for detailed installation.

## Who this is for

- Developers building LLM-powered tools who need structured execution, not just prompt templates
- Teams exploring context engineering and validation patterns
- Anyone who wants to run a model with tools, validate the output, and retry automatically

## What this is not

- **Not production-ready.** Auth is basic single-key. Rate limiting is per-process. No multi-tenant isolation.
- **Not an AI assistant.** SHARP is an orchestration layer, not a chatbot.
- **Not a deployment tool.** It's a development framework for building and testing LLM pipelines.
- **Not a replacement for Claude Code / ChatGPT.** It's infrastructure they could run on top of.

## Documentation

| Document | What it covers |
|---|---|
| [SETUP.md](SETUP.md) | Installation, prerequisites, environment variables |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, key modules |
| [CONFIG.md](CONFIG.md) | All config fields, defaults, env vars, stability |
| [EXAMPLES.md](EXAMPLES.md) | Minimal, tool-enabled, and HTTP API examples |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, code style, PR workflow |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Install to first run in under 5 minutes |
| [docs/EXTENDING.md](docs/EXTENDING.md) | Tools, validators, hooks, providers, middleware |

## Testing

```bash
# Mocked tests (no API key required)
pytest tests/ -m "not llm_integration" -q

# LLM integration tests (requires GITHUB_TOKEN)
pytest tests/test_llm_integration.py -v -m llm_integration
```

603 unit tests verify plumbing and control flow. 10 integration tests verify real LLM output shape.

## Status

**Version 0.2.1 — Developer Preview**

Core pipeline is stable. Dashboard, HTTP API, MCP, and orchestration are experimental. See [docs/QUICKSTART.md](docs/QUICKSTART.md) for what works today.

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and workflow.

```bash
git clone https://github.com/shivamsingh-007/SHARP-The-Harness-System.git
cd SHARP-The-Harness-System
pip install -e ".[dev]"
pytest tests/ -m "not llm_integration" -q
```

---

<div align="center">

**[Setup](SETUP.md)** · **[Architecture](ARCHITECTURE.md)** · **[Config](CONFIG.md)** · **[Examples](EXAMPLES.md)** · **[Contributing](CONTRIBUTING.md)**

MIT License · [GitHub](https://github.com/shivamsingh-007/SHARP-The-Harness-System)

</div>
