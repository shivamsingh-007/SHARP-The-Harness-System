# SHARP Limitations

## What SHARP Is Not

- **Not production-ready**: API key auth is basic (single key, no rotation), rate limiting is per-process, no multi-tenant isolation, no HTTPS
- **Not a replacement for Claude Code / ChatGPT**: SHARP is an orchestration layer, not an AI assistant
- **Not a framework for building AI products**: It's a research/development tool for exploring orchestration patterns

## Known Limitations

### Execution
- ReAct loop depends on LLM producing correct tool call format
- Native tool calling works best with OpenAI-format models (GPT-4o, Claude 3.5)
- Local models (Ollama) may not reliably produce tool calls
- Simple prompt detection is heuristic-based, not semantic

### Validation
- LLM judge requires a separate LLM call (cost + latency)
- Rule-based validation is keyword/pattern-based, not semantic
- Judge failure now fails closed (by design) — no fallback auto-pass

### Safety
- Budget enforcement is advisory, not hard-enforced at the provider level
- Circuit breaker tracks failures in-memory only (resets on restart)
- Rate limiting is per-IP in-memory token bucket (60 rpm general, 10 rpm expensive). Resets on restart.

### State
- Memory is file-based (JSON), not distributed
- Checkpoints are local to the filesystem
- No cross-session state sharing

### Dashboard
- FastAPI server is development-only (auth via X-API-Key header, no HTTPS)
- Dashboard metrics are in-memory (lost on restart)
- WebSocket broadcast is single-process only

### MCP
- MCP client connections are lazy (connect on first tool call)
- No MCP server discovery or auto-registration
- stdio transport requires the MCP server binary to be available

### Orchestrator
- Interface adapters are thin wrappers — no real vendor SDK integration
- Intent routing is keyword-based, not ML-based
- Audit log is JSON-lines file, not a database

### Testing
- LLM integration tests require real API keys (skipped in CI)
- Most tests use mocked providers — real LLM behavior not tested
- No load testing or performance benchmarks

## Security Notes

- HTTP API is localhost-only by default
- Authentication is API key-based (X-API-Key header); disabled only in dev_mode
- Shell commands in coding agent use `subprocess.run` with list args (no shell injection)
- Feature descriptions are passed to git commit — sanitize user input in production
