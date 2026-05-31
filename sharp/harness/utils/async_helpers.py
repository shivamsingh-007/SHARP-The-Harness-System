"""Async utility functions."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, TypeVar

T = TypeVar("T")


async def run_with_timeout(coro: Awaitable[T], timeout: float) -> T:
    """Run an async coroutine with a timeout.

    Raises:
        asyncio.TimeoutError: If the coroutine exceeds the timeout.
    """
    return await asyncio.wait_for(coro, timeout=timeout)


async def gather_with_limit(
    *coros: Awaitable[T],
    limit: int = 5,
) -> list[T]:
    """Run multiple coroutines with a concurrency limit."""
    semaphore = asyncio.Semaphore(limit)

    async def _limited(coro: Awaitable[T]) -> T:
        async with semaphore:
            return await coro

    return await asyncio.gather(*[_limited(c) for c in coros])


async def retry_async(
    func: Any,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """Retry an async function with exponential backoff."""
    last_exception = None
    current_delay = delay

    for attempt in range(max_attempts):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(current_delay)
                current_delay *= backoff

    raise last_exception  # type: ignore[misc]
