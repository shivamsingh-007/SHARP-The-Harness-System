"""Basic usage example for the Harness System."""

from sharp import HarnessEngine, HarnessConfig
from sharp.harness.core.types import RiskLevel


async def main():
    # Create engine with default config
    engine = HarnessEngine()

    # Register a simple tool
    @engine.tool(risk_level=RiskLevel.READ)
    async def search_web(query: str) -> str:
        """Search the web for information."""
        return f"Search results for: {query}"

    # Add some memory
    engine.add_memory("preferences", "User prefers concise responses")

    # Run a request
    result = await engine.run(
        "What is the capital of France?",
        docs=[{"name": "geography", "content": "France is a country in Europe."}],
    )

    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Attempts: {result.attempts}")
    print(f"Latency: {result.total_latency_ms:.0f}ms")
    print(f"Cost: ${result.total_cost_usd:.4f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
