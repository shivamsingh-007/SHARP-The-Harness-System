# SHARP HARNESS PREVENTION CHECKLIST

Before declaring any system or project healthy, verify every item on this checklist. No shortcuts. No assumptions. No "probably works."

---

## Installation & Startup

- [ ] 1. The package installs cleanly in a fresh environment.
  ```bash
  pip install -e ".[dev]" 2>&1 | tail -5
  ```
  Expected: `Successfully installed sharp-0.1.0`

- [ ] 2. The CLI entry point works after installation.
  ```bash
  sharp --help
  ```
  Expected: Shows available commands (run, validate, config-show, health, benchmark)

- [ ] 3. `python -m sharp` works if that is supported.
  ```bash
  python -m sharp --help
  ```
  Expected: Same output as `sharp --help`

- [ ] 4. The main engine run path completes without crashing.
  ```bash
  python -c "from sharp import HarnessEngine; import asyncio; r = asyncio.run(HarnessEngine().run('test')); print('OK' if r.success else 'FAIL')"
  ```
  Expected: `OK`

---

## Core Pipeline

- [ ] 5. Context curation, prompt composition, execution, validation, and retry all work together.
  ```bash
  python -m pytest tests/test_integration.py -v -k "end_to_end_simple" --tb=short
  ```
  Expected: PASSED

- [ ] 6. ReAct / CoT / ToT behavior is real if claimed, otherwise removed or marked experimental.
  ```bash
  python -c "
  from sharp.harness.execution.loop import ExecutionLoop
  import inspect
  source = inspect.getsource(ExecutionLoop.run)
  assert 'await provider.complete' in source, 'Loop does not call LLM'
  assert 'await self.tool_registry.execute' in source, 'Loop does not execute tools'
  print('ReAct loop is real')
  "
  ```
  Expected: `ReAct loop is real`

- [ ] 7. Sub-agents perform real work, not placeholder returns.
  ```bash
  python -c "
  from sharp.harness.execution.subagents import SubAgentManager
  import inspect
  source = inspect.getsource(SubAgentManager.spawn)
  assert 'return f\"[Sub-agent' not in source, 'Sub-agent returns placeholder'
  assert 'await provider.complete' in source, 'Sub-agent does not call LLM'
  print('Sub-agents are real')
  "
  ```
  Expected: `Sub-agents are real`

---

## Observability

- [ ] 8. Metrics receive real token, cost, and latency data.
  ```bash
  python -c "
  from sharp.harness.observability.metrics import MetricsCollector
  from sharp.harness.core.config import ObservabilityConfig
  m = MetricsCollector(ObservabilityConfig())
  m.start_trace('t1')
  m.end_trace('t1', tokens=100, cost=0.001, latency_ms=50)
  a = m.get_aggregate()
  assert a['total_tokens'] == 100, f'Expected 100 tokens, got {a[\"total_tokens\"]}'
  assert a['total_cost'] == 0.001, f'Expected 0.001 cost, got {a[\"total_cost\"]}'
  print('Metrics pipeline works')
  "
  ```
  Expected: `Metrics pipeline works`

- [ ] 9. Tracing and logging capture the important execution phases.
  ```bash
  python -c "
  from sharp.harness.observability.tracing import Tracer
  t = Tracer('test')
  with t.span('test_phase'):
      pass
  print('Tracing works')
  "
  ```
  Expected: `Tracing works`

---

## Safety & Enforcement

- [ ] 10. Safety rules, blocked commands, and approvals are actually enforced in code.
  ```bash
  python -c "
  import asyncio
  from sharp.harness.execution.tools import ToolRegistry
  from sharp.harness.core.config import ToolConfig
  from sharp.harness.core.types import ToolDefinition, RiskLevel
  config = ToolConfig(blocked_tools=['rm -rf', 'sudo'])
  r = ToolRegistry(config)
  async def cmd(c): return c
  r.register(cmd, ToolDefinition(name='run', description='', parameters={}))
  result = asyncio.run(r.execute('run', {'c': 'rm -rf /'}))
  assert not result.success, 'Blocked command was executed!'
  result2 = asyncio.run(r.execute('run', {'c': 'ls'}))
  assert result2.success, 'Safe command was blocked!'
  print('Blocked commands enforced')
  "
  ```
  Expected: `Blocked commands enforced`

- [ ] 11. MCP servers and LLM judge settings are clearly documented as enabled or disabled.
  ```bash
  python -c "
  import yaml
  with open('harness.yaml') as f:
      c = yaml.safe_load(f)
  assert c['validation']['llm_judge_enabled'] == True, 'LLM judge not enabled'
  assert c['mcp']['enabled'] == True, 'MCP not enabled'
  print('Defaults are correct')
  "
  ```
  Expected: `Defaults are correct`

---

## Configuration & Documentation

- [ ] 12. Every config field has a real consumer.
  ```bash
  python -c "
  from sharp.harness.core.config import HarnessConfig
  config = HarnessConfig()
  fields = list(config.model_fields.keys())
  for f in fields:
      assert getattr(config, f) is not None or f in ['llm'], f'Config field {f} has no value'
  print(f'All {len(fields)} config fields verified')
  "
  ```
  Expected: `All N config fields verified`

- [ ] 13. README matches actual implementation status.
  ```bash
  # Verify test count
  pytest --co -q 2>&1 | tail -1
  # Verify LOC
  find sharp/ -name "*.py" -exec cat {} + | wc -l
  # Verify module count
  find sharp/ -name "*.py" | wc -l
  ```
  Expected: Numbers match README claims

- [ ] 14. Benchmark numbers are backed by scripts and saved outputs.
  ```bash
  ls sharp/harness/benchmarks/
  python -m pytest tests/ -k benchmark -v --tb=short
  ```
  Expected: Benchmark directory exists and tests pass

---

## Testing

- [ ] 15. At least one smoke test for startup and one integration test for the full path.
  ```bash
  python -m pytest tests/test_integration.py -v --tb=short
  ```
  Expected: All integration tests PASSED

- [ ] 16. Async components have async tests.
  ```bash
  grep -c "async def test_" tests/test_loop.py tests/test_providers.py tests/test_engine.py tests/test_subagents.py
  ```
  Expected: Non-zero counts in each file

- [ ] 17. Provider calls are covered by mocked tests.
  ```bash
  python -m pytest tests/test_providers.py -v --tb=short
  ```
  Expected: All provider tests PASSED

- [ ] 18. Core modules are not only tested for construction but for behavior.
  ```bash
  # Verify behavioral tests exist (not just test_init)
  grep -c "def test_" tests/test_engine.py
  grep -c "test_init" tests/test_engine.py
  # Behavioral count should exceed init count
  ```
  Expected: More behavioral tests than init tests

---

## Cleanup & Release

- [ ] 19. Stub inventory is maintained and removed before release.
  ```bash
  python -c "
  import ast, os
  stubs = []
  for root, dirs, files in os.walk('sharp/harness'):
      for f in files:
          if f.endswith('.py'):
              path = os.path.join(root, f)
              content = open(path).read()
              if 'placeholder' in content.lower() or '# STUB' in content:
                  stubs.append(path)
  if stubs:
      print(f'Stubs found: {stubs}')
  else:
      print('No stubs found')
  "
  ```
  Expected: `No stubs found`

- [ ] 20. A short postmortem is written after every major failure.
  Every test failure, every production incident, every unexpected behavior gets a document:
  - What happened
  - Root cause
  - Fix applied
  - Prevention action (added to this checklist or RULE_BOOK.md)

- [ ] 21. Every issue gets a root cause, a fix, and a prevention action.
  No fix is complete without:
  1. A test that reproduces the original failure
  2. A code change that fixes the root cause
  3. A checklist entry or rule book addition that prevents recurrence

---

## Final Question

Before shipping, answer these five questions honestly:

> **22. What is real?**
> What works end-to-end with real LLM calls, real tools, real data?

> **What is stubbed?**
> What returns placeholder text or hardcoded values?

> **What is tested?**
> What has pytest tests that exercise behavior, not just constructors?

> **What is disabled?**
> What exists in code but is turned off by default?

> **What is missing?**
> What should exist but doesn't?

If you cannot answer all five with evidence, the system is not ready.

---

## Execution

Run the full checklist before:
- First release
- Every major version bump
- After any "quick fix" that touches core paths
- When onboarding a new contributor (have them run it)

Save the output. It is your proof of health.
