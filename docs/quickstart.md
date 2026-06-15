# Quickstart

Get SHARP running with a local LLM in under 2 minutes.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running

## 1. Install SHARP

```bash
git clone https://github.com/shivamsingh-007/SHARP-The-Harness-System.git
cd SHARP-The-Harness-System
pip install -e ".[dev]"
```

## 2. Pull a model

```bash
ollama pull llama3.1
```

This downloads ~4.9 GB. Only needed once.

## 3. Run your first query

```bash
sharp run "What is 2+2?"
```

Or with Python directly:

```python
import asyncio
from sharp import HarnessEngine, HarnessConfig

async def main():
    config = HarnessConfig.ollama()
    engine = HarnessEngine(config)
    result = await engine.run("What is 2+2?")
    print(result.output)

asyncio.run(main())
```

## 4. Use tools

```bash
sharp run "List files in the current directory"
sharp run "What time is it in UTC?"
sharp run "Calculate 15 * 37"
```

## 5. Run with a config file

```bash
sharp run "Explain Python decorators" --config harness.yaml
```

See `harness.yaml` in the repo root for an example config.

## Common options

| Flag | Description |
|---|---|
| `--model`, `-m` | Override the LLM model |
| `--config`, `-c` | Path to a YAML config file |
| `--verbose`, `-v` | Enable debug logging |

## Switching providers

```python
# OpenAI
config = HarnessConfig()
config.llm.provider = "openai"
config.llm.model = "gpt-4o"
config.llm.api_key = "sk-..."

# Anthropic
config = HarnessConfig()
config.llm.provider = "anthropic"
config.llm.model = "claude-3-5-sonnet-20241022"
config.llm.api_key = "sk-ant-..."

# Ollama (local, no key needed)
config = HarnessConfig.ollama()
```

## Troubleshooting

**"Connection refused"** — Ollama isn't running. Start it with `ollama serve`.

**Slow responses** — First request is slow as the model loads into VRAM. Subsequent requests are faster.

**Out of memory** — Use a smaller model: `ollama pull llama3.2:3b` then `config = HarnessConfig.ollama(model="llama3.2:3b")`.
