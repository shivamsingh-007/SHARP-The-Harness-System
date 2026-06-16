# Changelog

## [0.2.0] - 2026-06-16

### Security hardening completed
- API key auth via `X-API-Key` header (`SHARP_API_KEY` env var)
- `shell=False` + command allowlist on all subprocess calls
- Path validation on file tools (rejects traversal outside project root)
- Rate limiting (per-IP token bucket, 60 rpm general / 10 rpm expensive)
- CORS restricted to localhost origins
- WebSocket auth via `?token=` query param
- Human approval gate defaults to reject
- Persistence key sanitization (rejects traversal, null bytes, absolute paths)

### Truthful capability framing updated
- CoT/ToT strategies raise `NotImplementedError` (were silently ignored)
- PRODUCT_CONTRACT.md corrected (judge behavior, auth status)
- README metrics updated to actual counts (73 files, 10,871 lines, 603 tests)
- Architecture table includes all 15 zones

### CI and contract tests added
- GitHub Actions: lint, test with 70% coverage gate, integration on main
- Pre-commit hooks (ruff lint + format)
- 16 contract tests validating pipeline shapes
- `scripts/check_repo_metrics.py` prevents documentation drift
- `DashboardConfig` for auth, CORS, rate limit settings
- `HarnessConfig.github_models()` for GitHub Models API

### Removed
- Unused dependencies: `aiofiles`, `httpx`

### Gap-fill: critical coverage added (post-release)
- 47 MCP client tests (connection lifecycle, tool routing, error handling, discovery)
- 13 HTTP API isolation tests (auth enforcement, rate limiting, CORS, WebSocket auth, concurrency)
- 13 persistence restart survival tests (restart durability, corruption detection, key sanitization)
- 25 observability tests (error classification, span tracker, metrics, telemetry)
- Benchmark harness with reproducible runs, baseline comparison, labeled results
- Pytest timing plugin writing per-test duration to `test-results.json`
- Test count: 493 → 603

### Documentation restructured
- README rewritten from 488 to ~100 lines (install → quickstart → links)
- Public API facade: `from sharp.harness import Harness, HarnessConfig`
- `docs/QUICKSTART.md`: <5 min path with GitHub Models as canonical provider
- `docs/CANONICAL_EXAMPLES.md`: two blessed patterns (scripted + HTTP API)
- `docs/CONFIG_CONTRACT.md`: all ~40 config fields, defaults, stability, env vars
- `docs/EXTENDING.md`: 6 extension points with examples and contracts
- `docs/ARCHITECTURE.md`: runtime flow, state boundaries, key modules
- `examples/minimal.py`: runnable 20-line example
- Stale claims fixed in LIMITATIONS.md and PRODUCT_CONTRACT.md
- Deleted superseded docs: examples.md, engine.md, tools.md
