"""Tests for utils/async_helpers.py - Async utilities."""

import asyncio
import pytest
from sharp.harness.utils.async_helpers import run_with_timeout, gather_with_limit, retry_async


class TestRunWithTimeout:
    @pytest.mark.asyncio
    async def test_runs_within_timeout(self):
        async def quick():
            return "done"
        result = await run_with_timeout(quick(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        async def slow():
            await asyncio.sleep(10)
            return "done"
        with pytest.raises(asyncio.TimeoutError):
            await run_with_timeout(slow(), timeout=0.1)


class TestGatherWithLimit:
    @pytest.mark.asyncio
    async def test_basic_gather(self):
        async def task(x):
            return x * 2
        results = await gather_with_limit(task(1), task(2), task(3))
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        max_concurrent = 0
        current = 0

        async def task(x):
            nonlocal max_concurrent, current
            current += 1
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.01)
            current -= 1
            return x

        await gather_with_limit(*[task(i) for i in range(10)], limit=3)
        assert max_concurrent <= 3


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        call_count = 0
        async def success():
            nonlocal call_count
            call_count += 1
            return "done"

        result = await retry_async(success, max_attempts=3)
        assert result == "done"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        call_count = 0
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"

        result = await retry_async(
            fail_then_succeed,
            max_attempts=5,
            delay=0.01,
            exceptions=(ValueError,),
        )
        assert result == "done"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        async def always_fail():
            raise ValueError("always")

        with pytest.raises(ValueError):
            await retry_async(
                always_fail,
                max_attempts=3,
                delay=0.01,
                exceptions=(ValueError,),
            )
