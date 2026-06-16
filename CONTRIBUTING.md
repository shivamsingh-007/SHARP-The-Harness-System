# Contributing

Thanks for considering a contribution.

## Local development setup

```bash
git clone https://github.com/shivamsingh-007/SHARP-The-Harness-System.git
cd SHARP-The-Harness-System
pip install -e ".[dev]"
```

This installs SHARP in editable mode with dev tools (pytest, ruff).

## Code style

- **Formatter/Linter:** ruff (configured in `pyproject.toml`)
- **Type hints:** required on all public functions
- **Docstrings:** required on public classes and methods
- **Async:** prefer async over sync for I/O operations
- **No comments:** code should be self-documenting

Run checks:

```bash
ruff check .
ruff format --check .
```

Auto-fix:

```bash
ruff check --fix .
ruff format .
```

## Running tests

```bash
# Full mocked suite
pytest tests/ -m "not llm_integration" -q

# Specific zone
pytest tests/test_engine.py -v

# With coverage
pytest tests/ --cov=sharp --cov-report=term-missing
```

All tests must pass before submitting a PR. The CI gate requires 70% minimum coverage.

## Branch and PR workflow

1. **Fork** the repo or create a branch from `main`
2. **Make changes** — keep commits focused and well-described
3. **Run tests** — `pytest tests/ -m "not llm_integration" -q`
4. **Run linter** — `ruff check . && ruff format --check .`
5. **Open a PR** — describe what changed and why

### Commit messages

Use conventional style:

```
feat: add new validation rule type
fix: handle empty context gracefully
docs: update setup guide
test: add edge case for retry engine
```

### PR description

Include:
- What the change does
- Why it's needed
- How to test it
- Any breaking changes

## What kinds of contributions are welcome

- **Bug fixes** — always welcome
- **Test coverage** — fill gaps in existing tests
- **Documentation** — improve clarity, fix errors, add examples
- **New tools** — register via `@engine.tool()`
- **New validators** — add rule-based checks
- **New hooks** — lifecycle event handlers

### Please open an issue first for

- New features (so we can discuss scope)
- Large refactors (to avoid duplicated work)
- Provider integrations (to confirm approach)

## Project structure

```
sharp/harness/       Source code (15 modules)
tests/               Test suite (603 tests)
examples/            Runnable examples
docs/                Extended documentation
```

## Questions?

Open an issue or check the [README](README.md).
