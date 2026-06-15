"""SHARP MCP Server — exposes SHARP tools to Claude Code and other MCP clients.

Transport: stdio (default, for Claude Code) or streamable-http (future).

Usage:
    # Run as stdio server (default, for Claude Code):
    python -m sharp.harness.mcp

    # Run as HTTP server (future):
    python -m sharp.harness.mcp --transport http --port 8000

Claude Code config (add to ~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "sharp": {
          "command": "python",
          "args": ["-m", "sharp.harness.mcp"]
        }
      }
    }
"""

from __future__ import annotations

import argparse
import json
import time


def create_server():
    """Create and configure the SHARP MCP server.

    Returns a FastMCP server instance with 3 SHARP tools:
    - sharp_validate_output: Validate AI output for hallucinations
    - sharp_run_coding_session: Run a coding agent session
    - sharp_route_task: Route a task to the best AI interface/model
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError("MCP SDK not installed. Install with: pip install 'mcp>=1.20'")

    mcp = FastMCP("SHARP Orchestrator")

    # ── Tool 1: Validate Output ────────────────────────────────────────

    @mcp.tool()
    def sharp_validate_output(output: str, task_type: str = "general") -> str:
        """Validate AI output for hallucinations and quality issues.

        Use this tool to check if generated code, text, or answers are
        factual, complete, and free of hallucinations before presenting
        them to the user.

        Args:
            output: The AI-generated output to validate
            task_type: Type of task (rag, coding, general) — used for context
        """
        start = time.time()

        try:
            from sharp.harness.core.engine import HarnessEngine
            from sharp.harness.core.config import HarnessConfig

            config = HarnessConfig.default()
            engine = HarnessEngine(config)

            import asyncio
            result = asyncio.run(engine.validator.validate(
                response=output,
                user_request=f"Validate {task_type} output",
                context=f"Task type: {task_type}",
            ))

            latency_ms = (time.time() - start) * 1000

            response = {
                "passed": result.passed,
                "score": result.score,
                "issues": getattr(result, "issues", []),
                "latency_ms": round(latency_ms, 1),
            }
            return json.dumps(response)

        except Exception as e:
            return json.dumps({
                "passed": False,
                "score": 0.0,
                "issues": [str(e)],
                "error": str(e),
            })

    # ── Tool 2: Run Coding Session ─────────────────────────────────────

    @mcp.tool()
    def sharp_run_coding_session(project_root: str = ".", session_id: int = 1) -> str:
        """Run a coding agent session with the DPEVR workflow.

        Starts a session, runs the Detect-Prompt-Execute-Validate-Respond
        loop, and returns the session state with features and progress.

        Args:
            project_root: Path to the project root directory
            session_id: Numeric session ID for tracking
        """
        start = time.time()

        try:
            from sharp.harness.agents.coding import CodingAgent, CodingConfig

            config = CodingConfig(project_root=project_root)
            agent = CodingAgent(config=config)

            import asyncio
            state = asyncio.run(agent.start_session())

            features = agent.artifacts.read_features()
            progress = agent.artifacts.read_progress()

            latency_ms = (time.time() - start) * 1000

            response = {
                "status": "started",
                "session_id": session_id,
                "feature": features[-1] if features else None,
                "progress_count": len(progress),
                "project_root": project_root,
                "latency_ms": round(latency_ms, 1),
            }
            return json.dumps(response)

        except Exception as e:
            return json.dumps({
                "status": "failed",
                "error": str(e),
                "project_root": project_root,
            })

    # ── Tool 3: Route Task ─────────────────────────────────────────────

    @mcp.tool()
    def sharp_route_task(task: str, context: str = "{}") -> str:
        """Route a task to the best AI interface and model.

        Analyzes the task type, complexity, and context to recommend
        which AI interface (Claude, ChatGPT, etc.) and model to use.

        Args:
            task: Description of the task to route
            context: JSON string with context (files_involved, etc.)
        """
        start = time.time()

        try:
            from sharp.harness.orchestration.router import IntentRouter

            ctx = json.loads(context) if context else {}
            router = IntentRouter()
            decision = router.route(task, ctx)

            latency_ms = (time.time() - start) * 1000

            response = {
                "task_type": decision.task_type.value,
                "complexity": decision.complexity.value,
                "recommended_interface": decision.recommended_interface.value,
                "recommended_model": decision.recommended_model.value,
                "reasoning": decision.reasoning,
                "estimated_cost_usd": decision.estimated_cost_usd,
                "estimated_latency_ms": decision.estimated_latency_ms,
                "alternatives": {
                    "interfaces": [i.value for i in decision.alternative_interfaces],
                    "models": [m.value for m in decision.alternative_models],
                },
                "latency_ms": round(latency_ms, 1),
            }
            return json.dumps(response)

        except Exception as e:
            return json.dumps({
                "error": str(e),
                "task": task,
            })

    # ── Resources & Prompts ────────────────────────────────────────────

    @mcp.resource("info://sharp")
    def server_info() -> str:
        """Get information about this MCP server."""
        return (
            "SHARP MCP Server\n"
            "Tools: sharp_validate_output, sharp_run_coding_session, sharp_route_task\n"
            "Resources: info://sharp\n"
        )

    @mcp.prompt()
    def validate_with_sharp(output: str, task_type: str = "general") -> str:
        """Generate a prompt to validate output using SHARP.

        Args:
            output: The output to validate
            task_type: Type of task (rag, coding, general)
        """
        return (
            f"Use the sharp_validate_output tool to validate this output:\n\n"
            f"Task type: {task_type}\n"
            f"Output:\n{output}"
        )

    return mcp


def main():
    """Run the SHARP MCP server."""
    parser = argparse.ArgumentParser(description="SHARP MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport")
    parser.add_argument("--host", default="localhost", help="Host for HTTP transport")

    args = parser.parse_args()
    mcp = create_server()

    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        print(f"Starting SHARP MCP server on {args.host}:{args.port}")
        mcp.run(transport="streamable-http")
    else:
        print("Starting SHARP MCP server on stdio")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
