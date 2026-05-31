"""Example: Using MCP servers with the Harness System.

This example demonstrates:
1. Connecting to MCP servers (stdio and HTTP)
2. Using MCP tools in engine.run()
3. Reading MCP resources as context
4. Creating a custom MCP server
"""

import asyncio
from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import RiskLevel


async def example_basic_mcp():
    """Basic example: Connect to filesystem MCP server and use its tools."""
    config = HarnessConfig()
    config.mcp.enabled = True
    config.mcp.servers = [
        {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
            "transport": "stdio",
            "enabled": True,
        },
    ]

    # Use context manager for automatic MCP connection/cleanup
    async with HarnessEngine(config) as engine:
        # MCP tools are automatically discovered and registered
        print(f"Connected MCP servers: {engine.mcp_client.connected_servers}")
        print(f"Discovered tools: {list(engine.mcp_client.discovered_tools.keys())}")

        # Run with MCP tools available
        result = await engine.run(
            "List all Python files in the current directory"
        )
        print(f"Response: {result.output}")


async def example_multiple_servers():
    """Connect to multiple MCP servers simultaneously."""
    config = HarnessConfig()
    config.mcp.servers = [
        {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
            "enabled": True,
        },
        {
            "name": "github",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "enabled": True,  # Requires GITHUB_TOKEN env var
        },
    ]

    async with HarnessEngine(config) as engine:
        # List all discovered tools from all servers
        all_tools = engine.mcp_bridge.get_registered_tools()
        for tool in all_tools:
            print(f"  {tool.name} [{tool.risk_level.value}]: {tool.description[:60]}")


async def example_http_server():
    """Connect to a remote MCP server via HTTP."""
    config = HarnessConfig()
    config.mcp.servers = [
        {
            "name": "remote-api",
            "transport": "http",
            "url": "http://localhost:8000/mcp",
            "enabled": True,
        },
    ]

    async with HarnessEngine(config) as engine:
        result = await engine.run("What tools are available?")
        print(result.output)


async def example_manual_mcp_control():
    """Manual MCP connection control (without context manager)."""
    engine = HarnessEngine()

    # Manually connect to servers
    await engine.mcp_client.connect_stdio(
        "my-server",
        "python",
        ["-m", "sharp.harness.mcp.server"],
    )

    # Register tools manually
    tools = await engine.mcp_bridge.register_all_tools()
    print(f"Registered {len(tools)} MCP tools")

    # Run
    result = await engine.run("What time is it?")
    print(result.output)

    # Clean up
    await engine.close()


async def example_risk_overrides():
    """Override risk levels for specific MCP tools."""
    config = HarnessConfig()
    config.mcp.tool_risk_overrides = {
        "read_file": "read",       # Keep as read
        "write_file": "execute",   # Upgrade to execute (requires approval)
    }
    config.mcp.servers = [
        {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
            "enabled": True,
        },
    ]

    async with HarnessEngine(config) as engine:
        # write_file now requires approval due to override
        for tool in engine.mcp_bridge.get_registered_tools():
            print(f"  {tool.name}: risk={tool.risk_level.value}, approval={tool.requires_approval}")


async def example_custom_server():
    """Create and connect to a custom MCP server."""
    # First, start the custom server (in a real scenario, this would be separate)
    # python -m sharp.harness.mcp.server

    config = HarnessConfig()
    config.mcp.servers = [
        {
            "name": "custom",
            "command": "python",
            "args": ["-m", "sharp.harness.mcp.server"],
            "enabled": True,
        },
    ]

    async with HarnessEngine(config) as engine:
        # The custom server exposes get_current_time and calculate tools
        result = await engine.run("What time is it right now?")
        print(result.output)


async def example_mcp_resources_as_context():
    """MCP resources are automatically fed into context."""
    config = HarnessConfig()
    config.mcp.servers = [
        {
            "name": "knowledge-base",
            "transport": "http",
            "url": "http://localhost:8000/mcp",
            "enabled": True,
        },
    ]

    async with HarnessEngine(config) as engine:
        # MCP resources appear as context sources
        mcp_context = engine.mcp_bridge.get_context_from_resources()
        for source in mcp_context:
            print(f"  Context: {source.name} ({source.source_type})")

        # The resources are automatically included in context curation
        result = await engine.run("Summarize the knowledge base")


if __name__ == "__main__":
    # Run any example:
    # asyncio.run(example_basic_mcp())
    # asyncio.run(example_multiple_servers())
    # asyncio.run(example_http_server())
    # asyncio.run(example_manual_mcp_control())
    # asyncio.run(example_risk_overrides())
    # asyncio.run(example_custom_server())
    # asyncio.run(example_mcp_resources_as_context())

    print("MCP Integration Examples")
    print("=" * 50)
    print("Uncomment an example function above to run it.")
    print("\nPrerequisites:")
    print("  pip install 'mcp>=1.20'")
    print("  npm install -g @modelcontextprotocol/server-filesystem")
