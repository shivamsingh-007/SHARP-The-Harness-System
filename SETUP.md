# Setup

Get SHARP running on your machine.

## Prerequisites

- **Python 3.11+** — check with `python --version`
- **pip** — comes with Python
- **Git** — for cloning

Optional:
- **Ollama** — for local models ([install](https://ollama.com))
- **GitHub account** — for GitHub Models API (free tier available)

## Install

```bash
git clone https://github.com/shivamsingh-007/SHARP-The-Harness-System.git
cd SHARP-The-Harness-System
pip install -e .
```

For development (includes pytest, ruff):

```bash
pip install -e ".[dev]"
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | Yes (for GitHub Models) | GitHub PAT with `models:read` scope |
| `SHARP_API_KEY` | No | Dashboard HTTP API auth key |
| `SHARP_MODEL` | No | Override default model |

Set them:

```bash
export GITHUB_TOKEN=ghp_your_token_here
export SHARP_API_KEY=your_secret_key
```

Windows (PowerShell):

```powershell
$env:GITHUB_TOKEN="ghp_your_token_here"
$env:SHARP_API_KEY="your_secret_key"
```

## Running locally

### Minimal script

```bash
python examples/minimal.py
```

Expected output:

```
Rate limiting matters because it protects services from overload...

Tokens: 42 | Cost: $0.0001
```

### CLI

```bash
sharp run "What is the capital of France?"
sharp run "List files" --model gpt-4o-mini
sharp health
sharp config-show
```

## Running tests

```bash
# Mocked tests (fast, no API key)
pytest tests/ -m "not llm_integration" -q

# Integration tests (requires GITHUB_TOKEN)
pytest tests/test_llm_integration.py -v -m llm_integration

# With coverage
pytest tests/ --cov=sharp --cov-report=term-missing
```

## Common issues

**`ValueError: No GitHub token found`**

Set the `GITHUB_TOKEN` env var. See [Environment variables](#environment-variables).

**`ModuleNotFoundError: No module named 'sharp'`**

Run `pip install -e .` from the repo root.

**Ollama connection refused**

Start Ollama: `ollama serve`, then pull a model: `ollama pull llama3.1:8b`.

**Tests failing**

Run `pytest tests/ -m "not llm_integration" -q` — integration tests need a real API key.

## Next steps

- [EXAMPLES.md](EXAMPLES.md) — see working code
- [CONFIG.md](CONFIG.md) — configure models, validation, safety
- [ARCHITECTURE.md](ARCHITECTURE.md) — understand the system design
