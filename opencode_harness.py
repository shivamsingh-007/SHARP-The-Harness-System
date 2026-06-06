"""
OpenCode Harness Bridge
Connects SHARP harness system with the opencode CLI application.

Usage:
    from opencode_harness import OpenCodeHarness

    harness = OpenCodeHarness()
    result = await harness.execute("Create a React component for a todo list")
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import RiskLevel


class OpenCodeHarness:
    """Harness wrapper around opencode CLI operations.

    Provides context engineering, validation, and safety controls
    for opencode-assisted development tasks.
    """

    def __init__(self, config_path: str | None = None) -> None:
        if config_path and Path(config_path).exists():
            self.config = HarnessConfig.from_yaml(config_path)
        else:
            self.config = HarnessConfig.default()

        self.engine = HarnessEngine(self.config)
        self._register_tools()

    def _register_tools(self) -> None:
        """Register opencode operations as harness tools."""

        @self.engine.tool(risk_level=RiskLevel.READ, timeout=10.0)
        async def read_file(path: str) -> str:
            """Read contents of a file at the given path."""
            try:
                content = Path(path).read_text(encoding="utf-8")
                return content[:5000]  # Truncate for context budget
            except FileNotFoundError:
                return f"Error: File not found: {path}"
            except Exception as e:
                return f"Error reading {path}: {e}"

        @self.engine.tool(risk_level=RiskLevel.WRITE, timeout=15.0)
        async def write_file(path: str, content: str) -> str:
            """Write content to a file at the given path."""
            try:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(content, encoding="utf-8")
                return f"Successfully wrote to {path}"
            except Exception as e:
                return f"Error writing {path}: {e}"

        @self.engine.tool(risk_level=RiskLevel.WRITE, timeout=15.0)
        async def edit_file(path: str, old_string: str, new_string: str) -> str:
            """Edit a file by replacing old_string with new_string."""
            try:
                content = Path(path).read_text(encoding="utf-8")
                if old_string not in content:
                    return f"Error: old_string not found in {path}"
                new_content = content.replace(old_string, new_string, 1)
                Path(path).write_text(new_content, encoding="utf-8")
                return f"Successfully edited {path}"
            except Exception as e:
                return f"Error editing {path}: {e}"

        @self.engine.tool(risk_level=RiskLevel.READ, timeout=10.0)
        async def search_files(directory: str, pattern: str) -> str:
            """Search for files matching a glob pattern in a directory."""
            try:
                matches = list(Path(directory).glob(pattern))
                paths = [str(m) for m in matches[:50]]
                return json.dumps(paths, indent=2)
            except Exception as e:
                return f"Error searching: {e}"

        @self.engine.tool(risk_level=RiskLevel.READ, timeout=10.0)
        async def grep_content(directory: str, pattern: str) -> str:
            """Search file contents for a regex pattern."""
            try:
                results = []
                for path in Path(directory).rglob("*"):
                    if path.is_file() and path.suffix in (".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".md"):
                        try:
                            content = path.read_text(encoding="utf-8", errors="ignore")
                            for i, line in enumerate(content.splitlines(), 1):
                                if pattern.lower() in line.lower():
                                    results.append(f"{path}:{i}: {line.strip()}")
                                    if len(results) >= 30:
                                        break
                        except Exception:
                            continue
                    if len(results) >= 30:
                        break
                return "\n".join(results) if results else "No matches found"
            except Exception as e:
                return f"Error grepping: {e}"

        @self.engine.tool(risk_level=RiskLevel.EXECUTE, timeout=30.0, requires_approval=True)
        async def run_command(command: str, cwd: str = ".") -> str:
            """Execute a shell command and return its output."""
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=25,
                )
                output = result.stdout + result.stderr
                return output[:3000] if output else "Command completed with no output"
            except subprocess.TimeoutExpired:
                return "Error: Command timed out after 25 seconds"
            except Exception as e:
                return f"Error executing command: {e}"

    async def execute(self, request: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a request through the SHARP harness pipeline.

        Args:
            request: The development task/request.
            **kwargs: Additional context (docs, files, etc.)

        Returns:
            Dict with 'output', 'success', 'attempts', 'latency_ms', 'score'.
        """
        result = await self.engine.run(request, **kwargs)

        return {
            "output": result.output,
            "success": result.success,
            "attempts": result.attempts,
            "latency_ms": result.total_latency_ms,
            "cost_usd": result.total_cost_usd,
            "tokens": result.total_tokens,
            "score": result.validation_score,
            "error": result.error,
            "trace_id": result.trace_id,
        }

    def add_memory(self, key: str, value: str) -> None:
        """Add persistent memory to the harness."""
        self.engine.add_memory(key, value)

    def load_memory(self, path: str) -> None:
        """Load memory from a file."""
        self.engine.load_memory_file(path)


async def main():
    """Demo: run a request through the harness."""
    harness = OpenCodeHarness()

    result = await harness.execute(
        "Analyze the current project structure and suggest improvements"
    )

    print(f"\n{'='*60}")
    print(f"Success: {result['success']}")
    print(f"Output:\n{result['output']}")
    print(f"Attempts: {result['attempts']}")
    print(f"Latency: {result['latency_ms']:.0f}ms")
    print(f"Score: {result['score']:.2f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
