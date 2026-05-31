"""Memory manager - persistent memory across sessions (claude.md style)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryManager:
    """Manages persistent memory for the harness system.

    Memory types:
    - Session memory: cleared between runs
    - Persistent memory: saved to disk (like CLAUDE.md)
    - Episodic memory: past interactions (optional)
    """

    def __init__(self, memory_dir: str = ".harness/memory") -> None:
        self._memory_dir = Path(memory_dir)
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._session_memory: dict[str, str] = {}
        self._persistent_memory: dict[str, str] = {}
        self._load_persistent()

    def _load_persistent(self) -> None:
        """Load persistent memory from disk."""
        memory_file = self._memory_dir / "memory.json"
        if memory_file.exists():
            try:
                self._persistent_memory = json.loads(memory_file.read_text(encoding="utf-8"))
            except Exception:
                self._persistent_memory = {}

    def _save_persistent(self) -> None:
        """Save persistent memory to disk."""
        memory_file = self._memory_dir / "memory.json"
        memory_file.write_text(
            json.dumps(self._persistent_memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def set_session(self, key: str, value: str) -> None:
        """Set a session-scoped memory item."""
        self._session_memory[key] = value

    def set_persistent(self, key: str, value: str) -> None:
        """Set a persistent memory item (survives across runs)."""
        self._persistent_memory[key] = value
        self._save_persistent()

    def get(self, key: str) -> str | None:
        """Get a memory item (session first, then persistent)."""
        return self._session_memory.get(key) or self._persistent_memory.get(key)

    def get_all(self) -> dict[str, str]:
        """Get all memory items (merged, session overrides persistent)."""
        merged = {**self._persistent_memory, **self._session_memory}
        return merged

    def get_memory_summary(self) -> str:
        """Get a formatted summary of all memory for prompt injection."""
        all_memory = self.get_all()
        if not all_memory:
            return ""

        parts = ["## Memory / Context"]
        for key, value in all_memory.items():
            parts.append(f"\n### {key}\n{value}")
        return "\n".join(parts)

    def clear_session(self) -> None:
        """Clear session memory."""
        self._session_memory.clear()

    def delete_persistent(self, key: str) -> bool:
        """Delete a persistent memory item."""
        if key in self._persistent_memory:
            del self._persistent_memory[key]
            self._save_persistent()
            return True
        return False

    def load_from_file(self, file_path: str) -> None:
        """Load memory from a markdown/text file (like CLAUDE.md)."""
        path = Path(file_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            self._persistent_memory[path.name] = content
            self._save_persistent()
