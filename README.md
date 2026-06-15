<div align="center">

# ⚡ SHARP

### **S**ystem for **H**arnessing **A**ugmented **R**easoning and **T**ransforming **H**euristics

A general-purpose orchestration framework for LLM tools and agents with context engineering, prompt engineering, validation, and MCP integration.

**Security:** Designed for localhost development. Not production-hardened — CORS allows all origins, subprocess calls use `shell=True`, no auth on API endpoints.

---

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00FF00?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Tests: 472/472](https://img.shields.io/badge/Tests-472%20passed-44CC11?style=for-the-badge&logo=pytest&logoColor=white)](#-testing)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-FF6B35?style=for-the-badge&logo=modelcontextprotocol&logoColor=white)](#-mcp-integration)
[![Code: 8,648 LOC](https://img.shields.io/badge/Engine-8,648%20lines-8B5CF6?style=for-the-badge)](#-architecture)

<br />

```
███████╗██╗  ██╗  █████╗ ██████╗ ██████╗
██╔════╝██║  ██║ ██╔══██╗██╔══██╗██╔══██╗
███████╗███████║ ███████║██████╔╝██████╔╝
╚════██║██╔══██║ ██╔══██║██╔══██╗██╔═══╝
██████║██║  ██║ ██║  ██║██║  ██║██║
╚═════╝╚═╝  ╚═╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
```

**Context → Prompt → Execute → Validate → Retry → Respond**

</div>

---

## Why SHARP?

Most LLM agent frameworks give you a prompt and hope for the best. SHARP treats the **entire pipeline** as an engineered system — curating context, composing prompts, executing with tools, validating responses, and retrying with feedback.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SHARP Pipeline                                  │
│                                                                              │
│   User Request                                                               │
│       │                                                                      │
│       ▼                                                                      │
│   ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│   │ CONTEXT  │───▶│ PROMPT  │───▶│ EXECUTE  │───▶│ VALIDATE │───▶│RESPONSE│ │
│   │ Engineer │    │ Engineer│    │   LLM    │    │  Judge   │    │        │ │
│   └─────────┘    └─────────┘    └──────────┘    └────┬─────┘    └────────┘ │
│       ▲                                               │                     │
│       │              ┌──────────┐                     │                     │
│       │              │  SAFETY  │◀── budget ──────────┤                     │
│       │              │  circuit ─┼── breaker           │                     │
│       │              │  approval─┼── gates             │                     │
│       │              └──────────┘                     │                     │
│       │                                               │                     │
│       │              ┌──────────┐                     │                     │
│       └──────────────│  RETRY   │◀── feedback ────────┘                     │
│                      │  engine  │   (mutate context)                        │
│                      └──────────┘                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Performance

**Disclaimer:** These are synthetic microbenchmarks of mocked control flow. They measure in-memory operations (dict lookups, list appends, function calls) and do not reflect real workloads. Real LLM calls are orders of magnitude slower (seconds, not milliseconds).

| Operation | Throughput | Latency |
|:---|:---:|:---:|
| **Engine initialization** | — | **0.9 ms** |
| **Context curation** (20 docs + memory) | — | **21.8 ms** |
| **Prompt composition** | 2.6 calls/sec | **3.9 ms** |
| **Rule-based validation** | 3,125 calls/sec | **0.03 ms** |
| **Circuit breaker + budget check** | 730K checks/sec | **1.4 μs** |
| **MCP tool conversion** | 80K conversions/sec | **12.5 μs** |
| **MCP risk assessment** | 196K assessments/sec | **5.1 μs** |
| **Full pipeline** (mocked LLM, no real call) | — | **5.7 ms** |

```
Validation     ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.03ms
Engine Init    ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.9ms
Full Pipeline  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  5.7ms
Prompt Comp    ██████████████████████████░░░░░░░░░░░░░░░  3.9ms
Context Curate ████████████████████████████████████████░░  21.8ms
```

---

## 🏗️ Architecture

SHARP is organized into **10 engine zones**, each a self-contained module:

```
sharp/harness/
├── core/              Engine, config, types, errors
├── context/           Curator, memory, retrieval, compressor
├── prompt/            Composer, templates, token budget
├── execution/         LLM providers, tool registry, ReAct loop, sub-agents
├── validation/        LLM-as-judge, rule-based validator, retry engine
├── safety/            Circuit breaker, budget manager, permissions, HITL
├── state/             Checkpoints, sessions, persistence (file/Redis)
├── observability/     Metrics, tracing (OpenTelemetry), logging, telemetry
├── mcp/               MCP client, registry, bridge, optional server
└── utils/             Token counting, formatting, async helpers
```

| Zone | Files | Lines | Purpose |
|:---|:---:|:---:|:---|
| `core` | 5 | 839 | Engine orchestrator, config, shared types |
| `mcp` | 5 | 936 | MCP client, server registry, tool/resource/prompt bridge |
| `context` | 6 | 637 | Context curator, memory manager, document retrieval, compression |
| `execution` | 5 | 771 | Multi-provider LLM, tool governance, ReAct loop, sub-agents |
| `validation` | 5 | 432 | LLM judge, rule engine, retry with feedback mutation |
| `prompt` | 4 | 329 | Prompt composer, templates, token budget allocator |
| `safety` | 5 | 315 | Circuit breaker, budget limits, permissions, human-in-the-loop |
| `observability` | 5 | 289 | Metrics, OpenTelemetry tracing, structured logging |
| `state` | 4 | 241 | Checkpointing, session management, file/Redis persistence |
| `benchmarks` | 2 | 247 | Benchmark runner with 5 test types |
| `utils` | 4 | 146 | Token counting, async helpers, formatting |
| **Total** | **52** | **8,648** | |

---

## 🚀 Quick Start

### Installation

```bash
pip install -e ".[dev]"
```

### Minimal Example

```python
from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import RiskLevel

async def main():
    engine = HarnessEngine()

    @engine.tool(risk_level=RiskLevel.READ)
    async def search_web(query: str) -> str:
        """Search the web for information."""
        return f"Results for: {query}"

    result = await engine.run("What is the capital of France?")
    print(result.output)

asyncio.run(main())
```

### With Config File

```bash
sharp run "Explain Python decorators" --config harness.yaml
sharp run "List files in current dir" --model gpt-4o-mini
sharp health
sharp config-show
```

---

## 🔌 MCP Integration

SHARP connects to any **Model Context Protocol** server — stdio or HTTP — and automatically bridges tools, resources, and prompts into the pipeline.

```
   MCP Servers                    SHARP Engine
  ┌──────────────┐
  │ filesystem   │─── stdio ──┐
  ├──────────────┤             │    ┌──────────────────────────┐
  │ github       │─── stdio ──┼───▶│  MCP Client              │
  ├──────────────┤             │    │  ┌───────┐ ┌──────────┐  │
  │ postgres     │─── stdio ──┤    │  │Tools  │ │Resources │  │
  ├──────────────┤             │    │  └───┬───┘ └────┬─────┘  │
  │ custom API   │─── HTTP ───┘    │      │          │         │
  └──────────────┘                  │  ┌───▼───┐ ┌───▼──────┐  │
                                    │  │Bridge │ │ Bridge   │  │
                                    │  └───┬───┘ └───┬──────┘  │
                                    └──────┼─────────┼──────────┘
                                           │         │
                                    ┌──────▼───┐ ┌───▼──────────┐
                                    │ToolReg.  │ │ContextCurator│
                                    │(Execute) │ │(Context Eng.) │
                                    └──────────┘ └──────────────┘
```

### Connect to MCP Servers

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
    {
        "name": "api-server",
        "transport": "http",
        "url": "http://localhost:8000/mcp",
    },
]

async with HarnessEngine(config) as engine:
    # MCP tools auto-discovered and registered
    result = await engine.run("List all Python files and summarize them")
```

### Three-Primitive Bridge

| MCP Primitive | Maps To | Zone |
|:---|:---|:---|
| **Tools** | `ToolDefinition` + wrapper fn | Execution (ToolRegistry) |
| **Resources** | `ContextSource` | Context Engineering (Curator) |
| **Prompts** | Template definitions | Prompt Engineering (Composer) |

### Default MCP Servers

```python
from sharp.harness.mcp.registry import DEFAULT_MCP_SERVERS

# Built-in server definitions (disabled by default):
# - filesystem: npx @modelcontextprotocol/server-filesystem ./
# - github:     npx @modelcontextprotocol/server-github
# - postgres:   npx @modelcontextprotocol/server-postgres
```

---

## 🧠 Context Engineering

SHARP curates context from multiple sources before composing the prompt:

```python
engine = HarnessEngine()
engine.add_memory("preferences", "User prefers concise responses")
engine.load_memory_file("CLAUDE.md")

result = await engine.run(
    "Summarize this",
    docs=[
        {"name": "readme", "content": open("README.md").read()},
        {"name": "changelog", "content": open("CHANGELOG.md").read()},
    ],
)
```

**Curator operations:**
- **SELECT** — Gather sources by priority (user > memory > tools > docs)
- **DROP** — Remove empty, duplicate, or irrelevant content
- **COMPRESS** — Fit within token budget via truncation

---

## ✅ Validation

Responses pass through dual validation before reaching the user:

```python
config = HarnessConfig()
config.validation.max_retries = 3
config.validation.min_score = 0.7
config.validation.llm_judge_enabled = True
```

| Validator | Speed | What It Checks |
|:---|:---:|:---|
| **Rule-based** | 0.03 ms | Empty, too short, hallucination markers, JSON schema |
| **LLM-as-judge** | ~2s | Accuracy, relevance, completeness, clarity, safety |

If validation fails, the **retry engine** mutates the context with error feedback and re-runs until it passes (max N attempts).

---

## 🛡️ Safety

| Feature | Description |
|:---|:---|
| **Circuit Breaker** | Stops after N consecutive failures, auto-recovers after cooldown |
| **Budget Manager** | Hard limits on cost ($) and tokens per session |
| **Tool Permissions** | Risk-based classification: READ → WRITE → EXECUTE → CRITICAL |
| **Human Approval** | HITL gates for dangerous tool executions |

---

## ⚙️ Configuration

### `harness.yaml`

```yaml
llm:
  provider: openai
  model: gpt-4o
  temperature: 0.7
  max_tokens: 2048

validation:
  enabled: true
  level: strict
  llm_judge_enabled: true
  max_retries: 3
  min_score: 0.7

safety:
  circuit_breaker_enabled: true
  failure_threshold: 5
  max_cost_usd: 10.0
  max_tokens: 100000
  blocked_commands:
    - rm -rf
    - sudo
    - mkfs

mcp:
  enabled: true
  auto_discover: true
  servers:
    - name: filesystem
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "./"]
      enabled: true
```

### Programmatic Config

```python
from sharp import HarnessConfig

config = HarnessConfig()
config.llm.model = "claude-3-5-sonnet"
config.validation.max_retries = 5
config.mcp.auto_discover = True
```

### Ollama (Local LLM)

SHARP works with local models via Ollama. No API key required:

```python
from sharp import HarnessEngine, HarnessConfig

config = HarnessConfig.ollama()  # Uses llama3.1:8b at localhost:11434
engine = HarnessEngine(config)
result = await engine.run("What is 2+2?")
print(result.output)  # "The answer is 4."
```

Requirements:
- Ollama installed: `https://ollama.com`
- Model pulled: `ollama pull llama3.1`

---

## 🧪 Testing

```bash
# Run full suite (mocked tests, no LLM required)
pytest tests/ -v

# Run LLM integration tests (requires running Ollama instance)
pytest tests/test_llm_integration.py -v -m llm_integration

# Run specific zone
pytest tests/test_mcp/ -v
pytest tests/test_safety/ -v

# With coverage
pytest tests/ --cov=sharp --cov-report=term-missing
```

**Note:** 472 unit tests use mocked LLM responses and run without any external dependencies.
8 additional LLM integration tests (`test_llm_integration.py`) require a running Ollama instance
with `llama3.1:8b` pulled. CI runs only the mocked tests by default.

```
tests/test_engine.py         13/13  ✓  Core Engine
tests/test_loop.py           20/20  ✓  ReAct Execution Loop
tests/test_providers.py       9/9   ✓  LLM Providers
tests/test_subagents.py      11/11  ✓  Sub-Agents
tests/test_context.py        10/10  ✓  Context Engineering
tests/test_prompt.py          5/5   ✓  Prompt Engineering
tests/test_validation.py     11/11  ✓  Validation Zone
tests/test_validator.py       6/6   ✓  Response Validator
tests/test_judge.py           7/7   ✓  LLM Judge
tests/test_retry.py           3/3   ✓  Retry Engine
tests/test_safety.py         11/11  ✓  Safety Layer
tests/test_memory.py         12/12  ✓  Memory Manager
tests/test_retrieval.py       9/9   ✓  Document Retrieval
tests/test_checkpoint.py      7/7   ✓  Checkpoint Manager
tests/test_session.py         8/8   ✓  Session Manager
tests/test_persistence.py     7/7   ✓  File Backend
tests/test_metrics.py         7/7   ✓  Metrics Collector
tests/test_tracing.py         4/4   ✓  Tracer
tests/test_logging.py         4/4   ✓  Structured Logging
tests/test_human_approval.py  7/7   ✓  HITL Gates
tests/test_async_helpers.py   7/7   ✓  Async Utilities
tests/test_utils.py           5/5   ✓  Utilities
tests/test_integration.py    14/14  ✓  End-to-End Integration
tests/test_mcp/              18/18  ✓  MCP Module
tests/test_orchestration.py  73/73  ✓  Orchestration
tests/test_hooks.py          21/21  ✓  Hook System
tests/test_artifacts.py      21/21  ✓  Artifact Manager
tests/test_initializer.py     9/9   ✓  Initializer Agent
tests/test_coding_agent.py   37/37  ✓  Coding Agent
tests/test_multisession.py   12/12  ✓  Multi-Session
tests/test_http_api.py       15/15  ✓  HTTP API
tests/test_mcp_sharp_tools.py 14/14  ✓  MCP SHARP Tools
tests/test_dashboard.py      36/36  ✓  Dashboard
tests/test_orchestration.py  73/73  ✓  Orchestration Layer
─────────────────────────────────────
Total:                       472/472  ✓  All Passing
```

---

## 📦 Project Structure

```
sharp/                          # Python package (52 modules, 8,648 lines)
├── __init__.py                 # Public API: HarnessEngine, HarnessConfig, errors
├── __main__.py                 # python -m sharp
├── cli.py                      # CLI: sharp run, sharp health, sharp config-show
└── harness/
    ├── core/                   # Engine orchestrator, config, types, errors
    ├── context/                # Curator, memory, retrieval, compressor
    ├── prompt/                 # Composer, templates, budget
    ├── execution/              # Providers, tools, loop, sub-agents
    ├── validation/             # Judge, rules, validator, retry
    ├── safety/                 # Circuit breaker, budget, permissions, HITL
    ├── state/                  # Checkpoint, session, persistence
    ├── observability/          # Metrics, tracing, logging, telemetry
    ├── mcp/                    # MCP client, registry, bridge, server
    ├── benchmarks/             # Benchmark runner, 5 test types
    └── utils/                  # Tokens, async, format

tests/                          # Test suite (29 files, 2,805 lines)
examples/                       # Usage examples
harness.yaml                    # Default config
```

---

## 📊 Dependencies

| Package | Purpose |
|:---|:---|
| `pydantic` | Config and type validation |
| `litellm` | Multi-provider LLM (OpenAI, Anthropic, Google, etc.) |
| `tiktoken` | Token counting |
| `mcp` | Model Context Protocol SDK |
| `typer` + `rich` | CLI with formatted output |
| `pyyaml` | YAML config loading |
| `httpx` | Async HTTP client |
| `aiofiles` | Async file operations |

---

## 📜 License

MIT

---

<div align="center">

**Built with ⚡ by the SHARP project**

*Context → Prompt → Execute → Validate → Respond*

</div>
