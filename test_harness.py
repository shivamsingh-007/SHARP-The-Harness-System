"""Quick test for OpenCode Harness integration."""
import asyncio
from opencode_harness import OpenCodeHarness


async def test():
    harness = OpenCodeHarness()
    result = await harness.execute("List files in the current directory")
    
    success = result["success"]
    score = result["score"]
    latency = result["latency_ms"]
    output = result["output"][:300]
    
    print(f"Success: {success}")
    print(f"Score: {score:.2f}")
    print(f"Latency: {latency:.0f}ms")
    print(f"Output preview:\n{output}")


if __name__ == "__main__":
    asyncio.run(test())
