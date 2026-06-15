# Tools

SHARP tools are Python functions that the LLM can call during execution. The engine extracts parameter schemas from type hints, manages risk levels, and handles execution.

## Registering a tool

Use the `@engine.tool()` decorator:

```python
from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import RiskLevel

engine = HarnessEngine(HarnessConfig.ollama())

@engine.tool(risk_level=RiskLevel.READ)
async def search_web(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query
    """
    # Your implementation here
    return f"Results for: {query}"
```

The docstring becomes the tool description shown to the LLM. The function signature is converted to JSON Schema automatically.

## Tool schema

SHARP extracts the schema from your function signature:

```python
@engine.tool()
async def create_file(path: str, content: str, overwrite: bool = False) -> str:
    """Create a file with the given content.

    Args:
        path: Where to create the file
        content: File content
        overwrite: Whether to overwrite existing files
    """
    ...
```

Generates this JSON Schema:

```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string"},
    "content": {"type": "string"},
    "overwrite": {"type": "boolean", "default": false}
  },
  "required": ["path", "content"]
}
```

Parameters without defaults are required. Parameters with defaults are optional.

## Type mapping

| Python type | JSON Schema type |
|---|---|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |

## Risk levels

Every tool has a risk level that controls governance:

```python
from sharp.harness.core.types import RiskLevel

@engine.tool(risk_level=RiskLevel.READ)      # Safe, read-only
async def get_data(key: str) -> str: ...

@engine.tool(risk_level=RiskLevel.WRITE)     # Modifies state
async def save_data(key: str, value: str) -> str: ...

@engine.tool(risk_level=RiskLevel.EXECUTE)   # Runs commands
async def run_script(script: str) -> str: ...

@engine.tool(risk_level=RiskLevel.CRITICAL)  # Dangerous operations
async def delete_database(name: str) -> str: ...
```

| Level | Description | Default behavior |
|---|---|---|
| `READ` | Read-only, no side effects | Always allowed |
| `WRITE` | Modifies files or state | Always allowed |
| `EXECUTE` | Runs shell commands, scripts | Requires approval |
| `CRITICAL` | Destructive operations | Requires approval |

## Approval gates

Tools with `EXECUTE` or `CRITICAL` risk levels require approval by default:

```python
config = HarnessConfig()
config.safety.approval_mode = "risky_only"  # default
# Options: "all", "risky_only", "none"
```

You can override per-tool:

```python
@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=False)
async def run_safe_script(script: str) -> str:
    """Run a pre-approved script."""
    ...
```

## Blocked tools

Block specific tools by name:

```python
config = HarnessConfig()
config.tools.blocked_tools = ["run_shell", "delete_file"]
```

Or block command patterns in arguments:

```python
config.safety.blocked_commands = ["rm -rf", "sudo", "mkfs"]
```

## Built-in tools

SHARP registers 6 tools by default:

| Tool | Description | Risk |
|---|---|---|
| `get_current_time` | Get UTC time | READ |
| `calculate` | Safe math evaluation (AST-based, no `eval()`) | READ |
| `read_file` | Read file contents (truncated at 5K chars) | READ |
| `list_directory` | List files in a directory | READ |
| `search_files` | Glob pattern search | READ |
| `grep_content` | Regex search through file contents | READ |

Plus one built-in sub-agent tool:

| Tool | Description | Risk |
|---|---|---|
| `delegate_to_agent` | Delegate task to a sub-agent (researcher, coder, reviewer) | READ |

## Listing tools

```python
tools = engine.tool_registry.list_tools()
for t in tools:
    print(f"{t.name}: {t.description} (risk: {t.risk_level.value})")
```

## Tool execution flow

When the LLM calls a tool:

1. **Permission check** — Is the tool blocked? Does it need approval?
2. **Blocked command check** — Do any arguments contain blocked patterns?
3. **Execution** — Call the async function with the provided arguments
4. **Timeout** — Cancel if execution exceeds the timeout (default 30s)
5. **Truncation** — Truncate output if it exceeds `max_output_tokens`
6. **Recording** — Log the execution in the audit trail

## Sub-agents

Register specialized agents that the LLM can delegate to:

```python
from sharp.harness.execution.subagents import SubAgentDefinition

engine.subagent_manager.register(SubAgentDefinition(
    name="data_analyst",
    role="Data Analyst",
    instructions="You are a data analyst. Analyze datasets and produce insights.",
))
```

The LLM can then call `delegate_to_agent(agent_name="data_analyst", task="Analyze sales data")`.

Default sub-agents: `researcher`, `coder`, `reviewer`.

## MCP tools

MCP servers provide additional tools that are automatically bridged:

```python
config = HarnessConfig()
config.mcp.servers = [
    {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"]},
]

async with HarnessEngine(config) as engine:
    # MCP tools are now available alongside built-in tools
    result = await engine.run("List files using the filesystem server")
```

MCP tools go through the same governance layer as built-in tools. You can override their risk levels:

```python
config.mcp.tool_risk_overrides = {
    "filesystem_write_file": "critical",
}
```
