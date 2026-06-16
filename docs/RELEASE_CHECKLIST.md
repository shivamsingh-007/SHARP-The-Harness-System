# SHARP Release Checklist — v0.2.0

## Pre-Release Verification

### Tests
- [x] `pytest tests/ -m "not llm_integration"` — 493 passed, 0 failed
- [x] `pytest tests/test_llm_integration.py` — passes with real API key (manual)

### Security Controls
- [x] API key auth via `X-API-Key` header (`SHARP_API_KEY` env var)
- [x] `shell=False` + command allowlist on all subprocess calls
- [x] Path validation on file tools (rejects traversal outside project root)
- [x] Rate limiting (per-IP token bucket, 60 rpm / 10 rpm expensive)
- [x] CORS restricted to localhost origins
- [x] WebSocket auth via `?token=` query param
- [x] Human approval gate defaults to reject
- [x] Persistence key sanitization (rejects `..`, null bytes, absolute paths)

### Bug Fixes (12/12 from prior session)
- [x] CRITICAL-1 through MEDIUM-2 — all verified passing

### Documentation
- [x] PRODUCT_CONTRACT.md exists and is accurate (v0.2.0)
- [x] README.md metrics verified against repository scan (73 files, 10,871 lines, 603 tests)
- [x] ARCHITECTURE.md documents all 15 zones
- [x] LIMITATIONS.md lists known limitations honestly
- [x] CHANGELOG.md documents v0.2.0 changes

### Configuration
- [x] No hardcoded API keys in source
- [x] No overclaims in README or docs
- [x] CoT/ToT raise `NotImplementedError` (not silently ignored)
- [x] Contract tests pass (16 tests validating shapes/behavior)

### Deferred to Next Maintenance Pass
- [ ] Per-test metrics tracking (timing output to `test-results.json`)
- [ ] Reproducible benchmark harness

## Release Steps
1. Verify all checklist items above
2. `git add . && git commit -m "release: v0.2.0 — security hardening and honest framing"`
3. `git tag v0.2.0`
4. `git push origin main --tags`

## Post-Release
- [ ] Run LLM integration tests with real API key
- [ ] Add test metrics tracking
- [ ] Add benchmark harness
