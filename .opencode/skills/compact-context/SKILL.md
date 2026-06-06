---
name: compact-context
description: Use when working with context compression, token optimization, or managing LLM conversation context. Covers the COMPACT system (Context Optimization for Model Processing & Adaptive Compression Technology) located at C:\Users\shiva\OneDrive\Documents\Context system. Use for context compression, history reduction, tool output optimization, auto-compaction, and MCP integration tasks.
---

# COMPACT Context System

Production-grade context compression for LLM agents. 60-70% fewer tokens, same answers.

## Location

Source: `C:\Users\shiva\OneDrive\Documents\Context system`

## Quick Usage

### Python API

```python
from context_system import ContextManager

mgr = ContextManager()
r1 = await mgr.process_request("conversation-id", "What is Python?")
stats = mgr.get_stats("conversation-id")
```

### CLI

```bash
# From the Context system directory
cd "C:\Users\shiva\OneDrive\Documents\Context system"

# Interactive chat
context-system chat "Explain async Python"

# Compress text
context-system compress "Your long text here..." --strategy truncation

# Run benchmarks
context-system benchmark --test all
```

### Server

```bash
context-system serve --port 8000
# or
docker-compose up
```

## Architecture

```
Client → FastAPI Gateway → ContextManager Orchestrator
  ├── Usage Check (>90%) → Auto-Compaction
  ├── Strategy Selection:
  │   ├── <70%  → Truncation (sliding window, O(1))
  │   ├── 70-95% → Summarization (LLM-based)
  │   └── >95% → Token Compression (signal-based)
  ├── Tool Output Reduction:
  │   ├── Observation Masking (keep last 5 verbatim)
  │   └── Targeted Summary (LLM compress)
  └── Build OptimizedContext → Ready for LLM
```

## Compression Strategies

| Strategy | Method | Speed | When |
|----------|--------|-------|------|
| Truncation | Sliding window | O(1) | <70% usage |
| Summarization | LLM rolling summary | ~2s | >95% usage |
| Token Compression | Signal-based filtering | O(n) | 70-95% usage |
| RAG Retrieval | Vector DB retrieval | ~100ms | Any |

## Configuration

Edit `configs/default.yaml` in the Context system directory:

```yaml
max_tokens: 128000
compaction_threshold: 0.90
strategy:
  truncation_threshold: 0.70
  summarization_threshold: 0.95
history:
  truncation_window_tokens: 4000
  summarization_model: "gpt-4o-mini"
tool_output:
  masking_enabled: true
  recent_observations_verbatim: 5
compaction:
  enabled: true
  keep_last_n_messages: 20
llm:
  provider: "openai"
  model: "gpt-4o"
mcp:
  enabled: true
  server_name: "context-engine"
```

## API Endpoints

- `POST /v1/chat` - Send message, get optimized context
- `POST /v1/compress` - Compress text directly
- `GET /v1/stats/{conversation_id}` - Compression stats
- `DELETE /v1/conversations/{conversation_id}` - Clear conversation
- `GET /health` - Health check

## Integration with Harness

When working on the harness system and context compression is needed:

1. Import from the context system: `from context_system import ContextManager`
2. The context system directory must be on `PYTHONPATH` or installed via `pip install -e "C:\Users\shiva\OneDrive\Documents\Context system[all]"`
3. Default config loads from `configs/default.yaml` in the context system root

## Dependencies

```bash
pip install -e "C:\Users\shiva\OneDrive\Documents\Context system[all]"
```

Key deps: fastapi, chromadb, redis, tiktoken, pydantic, httpx
