"""Hook system for lifecycle events in the SHARP harness.

Provides a registry for async hook handlers that fire at specific
points in the engine lifecycle. Hooks can inspect and mutate context,
and can cancel actions by setting ctx.cancel = True.

Usage:
    registry = HookRegistry()

    async def my_hook(ctx: HookContext) -> None:
        print(f"Fired at {ctx.event.value}")
        ctx.data["custom_key"] = "value"

    registry.register(HookEvent.SESSION_START, my_hook)
    ctx = await registry.fire(HookEvent.SESSION_START, HookContext(event=HookEvent.SESSION_START))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class HookEvent(Enum):
    """Lifecycle events where hooks can fire."""

    SESSION_START = "session_start"
    """Fired after pre-flight checks, before context engineering."""

    SESSION_END = "session_end"
    """Fired after storing output, before returning HarnessResult."""

    BEFORE_EXECUTE = "before_execute"
    """Fired before LLM execution (ReAct loop or direct call)."""

    AFTER_EXECUTE = "after_execute"
    """Fired after successful validation, before returning result."""

    ON_VALIDATION_FAILURE = "on_validation_failure"
    """Fired when validation fails (before retry)."""

    ON_RETRY = "on_retry"
    """Fired when retry engine mutates context."""


@dataclass
class HookContext:
    """Mutable context passed to hook handlers.

    Hooks can read and modify data. Setting cancel=True
    signals the engine to skip the current action.
    """

    event: HookEvent
    data: dict[str, Any] = field(default_factory=dict)
    cancel: bool = False


HookHandler = Callable[[HookContext], Awaitable[None]]


class HookRegistry:
    """Registry for lifecycle hook handlers.

    Handlers are async callables that receive a HookContext.
    Multiple handlers can register for the same event.
    Handlers fire in registration order.
    """

    def __init__(self) -> None:
        self._hooks: dict[HookEvent, list[HookHandler]] = {}

    def register(self, event: HookEvent, handler: HookHandler) -> None:
        """Register a handler for a lifecycle event.

        Args:
            event: The lifecycle event to listen for.
            handler: Async callable that receives HookContext.
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
        logger.debug(f"Registered hook for {event.value}: {handler.__qualname__}")

    def unregister(self, event: HookEvent, handler: HookHandler) -> None:
        """Remove a handler from an event.

        Args:
            event: The event to remove from.
            handler: The handler to remove.
        """
        if event in self._hooks:
            self._hooks[event] = [h for h in self._hooks[event] if h is not handler]

    def clear(self, event: HookEvent | None = None) -> None:
        """Remove all handlers, or all handlers for a specific event.

        Args:
            event: If provided, clear only this event's handlers.
                   If None, clear all handlers.
        """
        if event is None:
            self._hooks.clear()
        else:
            self._hooks.pop(event, None)

    def has_hooks(self, event: HookEvent) -> bool:
        """Check if any handlers are registered for an event."""
        return bool(self._hooks.get(event))

    def handler_count(self, event: HookEvent) -> int:
        """Return the number of handlers registered for an event."""
        return len(self._hooks.get(event, []))

    async def fire(self, event: HookEvent, ctx: HookContext | None = None) -> HookContext:
        """Fire all handlers for an event.

        Args:
            event: The event to fire.
            ctx: Optional pre-built context. If None, creates a new one.

        Returns:
            The (possibly mutated) HookContext after all handlers ran.
            If any handler set cancel=True, iteration stops early.
        """
        if ctx is None:
            ctx = HookContext(event=event)

        handlers = self._hooks.get(event, [])
        if not handlers:
            return ctx

        logger.debug(f"Firing {len(handlers)} hooks for {event.value}")

        for handler in handlers:
            if ctx.cancel:
                logger.debug(f"Hook cancelled at {handler.__qualname__}")
                break
            try:
                await handler(ctx)
            except Exception as e:
                logger.error(f"Hook handler {handler.__qualname__} failed: {e}")

        return ctx
