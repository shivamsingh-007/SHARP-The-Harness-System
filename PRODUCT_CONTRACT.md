# PRODUCT_CONTRACT.md

## What SHARP Is

**SHARP is a modular orchestration framework for LLM pipelines and tool-using agents, suitable today for local development, research workflows, coding assistance, and controlled API/MCP integrations, but not yet a hardened multi-tenant production platform.**

## What SHARP Does

- Runs a structured pipeline: context curation, prompt composition, LLM execution, validation, retry
- Executes tools via a ReAct loop (Thought, Action, Observation, Final Answer)
- Supports native OpenAI function calling and text-based ReAct fallback
- Provides 6 built-in tools: time, calculate, read_file, list_directory, search_files, grep_content
- Exposes an HTTP API (FastAPI) with route, validate, and coding session endpoints
- Exposes an MCP server (FastMCP) with 3 tools: validate_output, run_coding_session, route_task
- Manages coding sessions with features, progress tracking, and git integration
- Provides hooks for lifecycle events (session start/end, before/after execute, retry, etc.)
- Supports multiple LLM providers via LiteLLM (OpenAI, Anthropic, Google, Ollama)

## What SHARP Does Not Do

- Not production-ready: no auth, no database persistence, no streaming, no rate limiting
- Not a multi-tenant platform: state is in-memory, no request isolation by default
- Not a code generation IDE: the coding agent orchestrates features and tests, not full implementations
- Not a deployment tool: no CI/CD integration, no container management
- Not a real-time system: no WebSocket streaming of LLM tokens

## Supported Execution Modes

| Mode | Status | Notes |
|---|---|---|
| Direct library (`engine.run()`) | Stable | Primary usage pattern |
| HTTP API (FastAPI) | Experimental | Shared engine state, not concurrency-safe |
| MCP server (FastMCP) | Experimental | Creates new engine per tool call |
| CLI (`sharp run`) | Stable | Wraps direct library usage |

## Current Guarantees

| Subsystem | Status | What it does |
|---|---|---|
| ReAct loop | Stable | Tool calling with native + text fallback, repeated call detection |
| CoT/ToT strategies | Planned | Enum values defined, raises NotImplementedError if selected |
| Built-in tools | Stable | Time, calculate, file ops — all real implementations |
| Hook system | Stable | 10 lifecycle events, exception isolation, context mutation |
| Artifact system | Stable | Features (JSON) + Progress (JSON-lines), health checks, git integration |
| Context curation | Stable | Priority-based source selection, truncation, deduplication |
| Prompt composition | Stable | System prompt + tools + context assembly |
| Rule-based validation | Stable | Empty check, length check, hallucination markers |
| Unit tests | Stable | 493 tests, well-organized, mocked LLM |
| LLM integration | Experimental | Requires Ollama, 11 approval-style tests |
| Orchestrator | Experimental | Routes across interfaces, creates engine per request |
| Coding agent | Experimental | DPEVR loop, async path has known issues |
| LLM judge | Experimental | Auto-fails on evaluation failure (fail-closed); fragile JSON parsing |
| HTTP API | Experimental | API key auth via X-API-Key header (set SHARP_API_KEY env var) |
| MCP server | Experimental | Engine per call, no state persistence |

## Release Gate Policy

A feature cannot be claimed as "supported" unless all three are true:

1. **Code path exists** — the feature is implemented in production code, not just a stub
2. **Test exists** — at least one non-mocked test exercises the real execution path
3. **Example exists** — a working code snippet demonstrates the feature

A benchmark cannot be claimed unless labeled as one of:

- **Mocked** — LLM calls are mocked, measures control flow only
- **Synthetic** — Measures isolated component performance, not real workload
- **Real** — Runs against a live LLM with real prompts

## Version Policy

Current version: `0.2.0` — **Developer Preview**

This means:
- APIs may change without notice
- Not suitable for production workloads
- Known issues are documented in LIMITATIONS.md
- Contributions welcome, but expect breaking changes
