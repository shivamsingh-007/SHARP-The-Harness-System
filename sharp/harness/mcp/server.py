"""Optional MCP Server skeleton for running custom MCP servers.

This module provides a template for creating custom MCP servers
that can be connected to by the harness system.

Usage:
    # Run as stdio server:
    python -m sharp.harness.mcp.server

    # Run as HTTP server:
    python -m sharp.harness.mcp.server --transport http --port 8000
"""

from __future__ import annotations

import argparse
import datetime


def create_server():
    """Create and configure a custom MCP server.

    Returns a FastMCP server instance with example tools.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError("MCP SDK not installed. Install with: pip install 'mcp>=1.20'")

    mcp = FastMCP("Harness Custom Server")

    @mcp.tool()
    def get_current_time(timezone: str = "UTC") -> str:
        """Get the current date and time.

        Args:
            timezone: Timezone to return (UTC, local)
        """
        now = datetime.datetime.now()
        if timezone.upper() == "UTC":
            now = datetime.datetime.utcnow()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    @mcp.tool()
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression safely.

        Args:
            expression: Math expression to evaluate (e.g., "2 + 2", "3 * 4")
        """
        # Simple safe math evaluation
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Expression contains invalid characters"
        try:
            result = eval(expression)  # noqa: S307 - safe math only
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    @mcp.resource("info://server")
    def server_info() -> str:
        """Get information about this MCP server."""
        return (
            "Harness Custom MCP Server\n"
            "Provides: get_current_time, calculate tools\n"
            "Resources: info://server\n"
        )

    @mcp.prompt()
    def analyze_data(data: str, question: str) -> str:
        """Generate a prompt to analyze data.

        Args:
            data: The data to analyze
            question: The question to answer
        """
        return f"Analyze the following data and answer the question:\n\nData:\n{data}\n\nQuestion: {question}"

    return mcp


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="Harness Custom MCP Server")
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
        print(f"Starting MCP server on {args.host}:{args.port}")
        mcp.run(transport="streamable-http")
    else:
        print("Starting MCP server on stdio")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
