"""Example with tool execution and validation."""

from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import RiskLevel


async def main():
    # Configure with custom settings
    config = HarnessConfig()
    config.validation.max_retries = 2
    config.safety.max_cost_usd = 5.0

    engine = HarnessEngine(config)

    # Register multiple tools
    @engine.tool(risk_level=RiskLevel.READ)
    async def read_file(path: str) -> str:
        """Read a file's contents."""
        return f"Contents of {path}"

    @engine.tool(risk_level=RiskLevel.WRITE)
    async def write_file(path: str, content: str) -> str:
        """Write content to a file."""
        return f"Written to {path}"

    @engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True)
    async def run_command(command: str) -> str:
        """Execute a shell command."""
        return f"Output of: {command}"

    # Run with context
    result = await engine.run(
        "Read the config file and summarize it",
        docs=[
            {"name": "config", "content": "server:\n  port: 8080\n  host: localhost"},
            {"name": "readme", "content": "This is a demo application."},
        ],
    )

    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Validation Score: {result.validation_score:.2f}")

    # Check budget usage
    budget = engine.budget_manager.get_usage()
    print(f"\nBudget Usage:")
    print(f"  Tokens: {budget['session_tokens']}/{budget['token_limit']}")
    print(f"  Cost: ${budget['session_cost']:.4f}/${budget['cost_limit']:.2f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
