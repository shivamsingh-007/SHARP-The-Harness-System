# SHARP HARNESS RULE BOOK

These rules govern how the SHARP harness system is built, tested, documented, and released. Every contributor must follow them. No exceptions.

---

## 1. No Feature Without Real Execution

Never claim a feature is implemented unless the engine actually uses it in a real run path.

**What this means:** If `execution/loop.py` has a class but `engine.py` never calls it, the feature is not implemented. If `subagents.py` returns a hardcoded string, the feature is not implemented.

**How to verify:** Search `engine.py` for every component. Every zone must be invoked in `run()` or `_execute_with_retry()`.

---

## 2. No Stubs in Core Paths

Never keep stub modules in core execution paths without labeling them as stubs in code and docs.

**What this means:** If a function returns `"placeholder"` or `"not implemented"`, it must have a `# STUB:` comment and a TODO linking to the issue. Stubs are not allowed in the critical path without explicit disclosure.

**How to verify:** `grep -rn "placeholder\|stub\|not implemented\|TODO" sharp/harness/`

---

## 3. No README Overclaims

Never allow README claims to exceed what tests, scripts, or runnable code can prove.

**What this means:** If the README says "310 tests passing", there must be 310 tests in `tests/`. If it says "60-70% token reduction", there must be benchmark code that produces that number.

**How to verify:** `pytest --co -q | tail -1` counts tests. `python -m sharp.benchmark` must run.

---

## 4. No Benchmark Numbers Without Evidence

Never publish benchmark numbers without benchmark code, raw outputs, and repeatable conditions.

**What this means:** No performance claims in docs without a `benchmarks/` directory containing runnable scripts, logged outputs, and machine specs.

**How to verify:** `ls sharp/harness/benchmarks/` exists and `python -m sharp.benchmark --test all` produces output.

---

## 5. No Manual Test Counts

Never count tests by manual estimate when pytest can count them for you.

**What this means:** Run `pytest --co -q | tail -1` to get the exact count. Never say "approximately N tests".

**How to verify:** `pytest --co -q | tail -1` must match the number in README.

---

## 6. CLI Must Be Tested

Never leave the CLI or package entry point untested.

**What this means:** `python -m sharp --help` must work. `sharp --help` must work. Importing `from sharp.cli import app` must work.

**How to verify:** `python -c "from sharp.cli import app; print('OK')"`

---

## 7. No Broken Package Imports

Never allow root-level files to break installed package imports.

**What this means:** If `cli.py` is at the root, `sharp/cli.py` must re-export `app`. `__main__.py` must import from the correct path. Running `python -m sharp` must not fail with `ModuleNotFoundError`.

**How to verify:** `python -c "from sharp import HarnessEngine; print('OK')"`

---

## 8. Execution Loop Must Drive Behavior

Never let the execution loop exist as state tracking only; it must drive behavior.

**What this means:** `ExecutionLoop.run()` must call the LLM, parse responses, execute tools, and record observations. State tracking without orchestration is a skeleton, not a feature.

**How to verify:** `ExecutionLoop.run()` must contain `await provider.complete()`, `await tool_registry.execute()`, and `self.record_observation()`.

---

## 9. Sub-Agents Must Make Real Calls

Never let sub-agents return placeholder text instead of real model/tool execution.

**What this means:** `SubAgentManager.spawn()` must call `provider.complete()` and return the actual model response, not a formatted string.

**How to verify:** `SubAgentManager.spawn()` must contain `await provider.complete()`.

---

## 10. Safety Features Must Be Enabled

Never ship safety or judge features as "enabled" if they are disabled by default.

**What this means:** `harness.yaml` must have `llm_judge_enabled: true`, `mcp.enabled: true`, `circuit_breaker_enabled: true`. If a feature is production-ready, it must be on by default.

**How to verify:** `grep -E "enabled:|judge_enabled:" harness.yaml` must show `true` for all safety features.

---

## 11. No Orphan Config Keys

Never keep config keys that have no code consumer.

**What this means:** Every field in `HarnessConfig` must be read by at least one module. If `SafetyConfig.blocked_commands` exists, something must use `config.safety.blocked_commands`.

**How to verify:** `grep -rn "config\.\|self\.config\." sharp/harness/ | grep -v "test_"` must show usage for every config field.

---

## 12. No Constructor-Only Tests

Never treat constructor tests as proof of system correctness.

**What this means:** `test_init_default` proves the constructor works, not the system. Every component must have at least one test that exercises its primary behavior (e.g., `engine.run()`, `loop.run()`, `provider.complete()`).

**How to verify:** Every test file must have at least one test with `await` or a behavioral assertion beyond `assert x is not None`.

---

## 13. No Release Without Smoke + Integration Tests

Never merge a release without at least one smoke test and one integration test for the main path.

**What this means:** `tests/test_integration.py` must exist with end-to-end tests that exercise the full pipeline (context -> prompt -> execute -> validate).

**How to verify:** `pytest tests/test_integration.py -v` must pass.

---

## 14. No Ignored Async

Never ignore async behavior in an async architecture.

**What this means:** All LLM calls, tool executions, and MCP operations must be `async/await`. Tests must use `pytest-asyncio`. No `asyncio.run()` inside async functions.

**How to verify:** `grep -rn "def.*async" sharp/harness/` must show async for all I/O-bound methods.

---

## 15. No Doc-Code Drift

Never let docs, claims, and code drift apart.

**What this means:** If the README says "53 modules", `find sharp/ -name "*.py" | wc -l` must equal 53. If it says "ReAct loop", the code must implement Think->Act->Observe.

**How to verify:** Every README claim must have a corresponding verification command.

---

## 16. No Hidden Uncertainty

Never hide uncertainty; clearly mark what is real, partial, experimental, or disabled.

**What this means:** Use comments like `# EXPERIMENTAL:`, `# PARTIAL:`, `# STUB:` to mark incomplete features. Don't ship stubs as features.

**How to verify:** `grep -rn "EXPERIMENTAL\|PARTIAL\|STUB" sharp/harness/` must show clear markers.

---

## 17. No Memory-Based Claims

Never rely on memory; every important claim must have evidence.

**What this means:** Don't say "I tested it earlier". Run the test again. Don't say "it should work". Run the code. Every claim must be backed by a command that produced the expected output.

**How to verify:** Every claim in a PR or commit message must reference a test run or command output.

---

## 18. No Symptom-Only Fixes

Never fix symptoms while leaving the root cause untracked.

**What this means:** If a test fails, don't just change the assertion. Understand why the code produces the wrong behavior and fix the code. If the root cause is known but not fixed, file it as a TODO with context.

**How to verify:** Every fix must include a test that reproduces the original failure.

---

## 19. No "Works On My Machine"

Never accept "works on my machine" as validation.

**What this means:** Tests must pass in CI. If a test only works locally, it's not a test -- it's a hypothesis. Fix the test or mark it as `@pytest.mark.skip(reason="...")` with a clear explanation.

**How to verify:** `pytest tests/ -v` must pass with zero failures.

---

## 20. No Release Without Full Cycle

Never release a harness until the package installs, the CLI runs, and the engine completes one full cycle.

**What this means:** Before any release:
1. `pip install -e .` succeeds
2. `python -m sharp --help` works
3. `python -c "from sharp import HarnessEngine; import asyncio; print(asyncio.run(HarnessEngine().run('test')))"` completes
4. `pytest tests/ -v` shows all tests passing

**How to verify:** Run all 4 commands in sequence. Any failure blocks the release.

---

## Enforcement

These rules are enforced by:
- **Code review:** Every PR must demonstrate compliance
- **CI:** `pytest` must pass, LOC must match claims, CLI must work
- **Pre-release checklist:** Run all verification commands before tagging

Violations are tracked as issues with the `rule-book` label.
