"""In-memory token bucket rate limiter for FastAPI.

IMPORTANT: Buckets are per-process. Under multiple workers (e.g., uvicorn
with --workers > 1), limits will fragment unless state is centralized
(e.g., Redis). For single-process deployments, this is sufficient.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass
class _TokenBucket:
    """Simple token bucket for rate limiting."""

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def allow(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP token bucket rate limiter.

    Args:
        general_rpm: Requests per minute for general endpoints.
        expensive_rpm: Requests per minute for expensive endpoints.
        expensive_paths: URL path prefixes that use the stricter limit.
    """

    EXPENSIVE_PATHS = frozenset({"/api/engine/run", "/api/coding/session"})

    def __init__(
        self,
        app: Any,
        general_rpm: int = 60,
        expensive_rpm: int = 10,
    ) -> None:
        super().__init__(app)
        self._general_capacity = general_rpm
        self._general_refill = general_rpm / 60.0  # tokens per second
        self._expensive_capacity = expensive_rpm
        self._expensive_refill = expensive_rpm / 60.0
        self._buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(self._general_capacity, self._general_refill)
        )
        self._expensive_buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(self._expensive_capacity, self._expensive_refill)
        )
        self._last_cleanup = time.monotonic()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _cleanup_stale_buckets(self) -> None:
        """Periodically remove stale buckets to prevent memory leaks."""
        now = time.monotonic()
        if now - self._last_cleanup < 300:  # every 5 minutes
            return
        self._last_cleanup = now
        stale_threshold = now - 600  # 10 minutes idle
        stale_ips = [
            ip for ip, bucket in self._buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for ip in stale_ips:
            del self._buckets[ip]
            self._expensive_buckets.pop(ip, None)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Any:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_expensive = any(
            request.url.path.startswith(p) for p in self.EXPENSIVE_PATHS
        )

        if is_expensive:
            bucket = self._expensive_buckets[client_ip]
        else:
            bucket = self._buckets[client_ip]

        if not bucket.allow():
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again shortly."},
                headers={"Retry-After": "1"},
            )

        self._cleanup_stale_buckets()
        return await call_next(request)
