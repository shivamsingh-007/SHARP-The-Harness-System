"""Persistence backends - file, Redis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class PersistenceBackend(Protocol):
    """Protocol for persistence backends."""

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> bool: ...
    def list_keys(self, prefix: str = "") -> list[str]: ...


class FileBackend:
    """File-based persistence backend."""

    def __init__(self, base_dir: str = ".harness/storage") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> str | None:
        """Get a value by key."""
        safe_key = self._sanitize_key(key)
        path = self._base_dir / f"{safe_key}.json"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def set(self, key: str, value: str) -> None:
        """Set a value by key."""
        safe_key = self._sanitize_key(key)
        path = self._base_dir / f"{safe_key}.json"
        path.write_text(value, encoding="utf-8")

    def delete(self, key: str) -> bool:
        """Delete a value by key."""
        safe_key = self._sanitize_key(key)
        path = self._base_dir / f"{safe_key}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with optional prefix."""
        keys = []
        sanitized_prefix = prefix.replace(":", "-")
        for path in self._base_dir.glob(f"{sanitized_prefix}*.json"):
            keys.append(path.stem)
        return keys

    @staticmethod
    def _sanitize_key(key: str) -> str:
        """Sanitize key for filesystem.

        Rejects keys containing path traversal, null bytes, or absolute paths.
        """
        if "\0" in key:
            raise ValueError(f"Invalid key: contains null byte")
        if key.startswith("/") or key.startswith("\\"):
            raise ValueError(f"Invalid key: absolute path not allowed: {key}")
        if ".." in key:
            raise ValueError(f"Invalid key: path traversal not allowed: {key}")
        return key.replace(":", "-").replace("/", "-").replace("\\", "-")


class RedisBackend:
    """Redis-based persistence backend."""

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            raise ImportError("Redis backend requires 'redis' package: pip install redis")

    def get(self, key: str) -> str | None:
        """Get a value by key."""
        return self._client.get(f"harness:{key}")

    def set(self, key: str, value: str) -> None:
        """Set a value by key."""
        self._client.set(f"harness:{key}", value)

    def delete(self, key: str) -> bool:
        """Delete a value by key."""
        return bool(self._client.delete(f"harness:{key}"))

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with optional prefix."""
        pattern = f"harness:{prefix}*"
        keys = self._client.keys(pattern)
        return [k.replace("harness:", "", 1) for k in keys]
