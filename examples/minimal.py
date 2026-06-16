"""Minimal SHARP example — summarize a topic using GitHub Models.

Prerequisites:
    export GITHUB_TOKEN=your_token_here
    python examples/minimal.py
"""

import asyncio

from sharp.harness import Harness, HarnessConfig


async def main() -> None:
    config = HarnessConfig.github_models(model="gpt-4o-mini")

    async with Harness(config=config) as engine:
        result = await engine.run(
            "Summarize why rate limiting matters in one paragraph."
        )

        print(result.output)
        print(f"\nTokens: {result.total_tokens} | Cost: ${result.total_cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
