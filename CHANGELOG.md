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
- README metrics updated to actual counts (73 files, 10,871 lines, 493 tests)
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

### Deferred to next maintenance pass
- Per-test metrics tracking (timing output to `test-results.json`)
- Reproducible benchmark harness
