"""Tests for the hook system."""

import pytest
from sharp.harness.execution.hooks import HookRegistry, HookEvent, HookContext


class TestHookEvent:
    def test_all_events_exist(self):
        events = [
            HookEvent.SESSION_START,
            HookEvent.SESSION_END,
            HookEvent.BEFORE_EXECUTE,
            HookEvent.AFTER_EXECUTE,
            HookEvent.ON_VALIDATION_FAILURE,
            HookEvent.ON_RETRY,
        ]
        assert len(events) == 6

    def test_event_values_are_strings(self):
        assert HookEvent.SESSION_START.value == "session_start"
        assert HookEvent.SESSION_END.value == "session_end"


class TestHookContext:
    def test_default_context(self):
        ctx = HookContext(event=HookEvent.SESSION_START)
        assert ctx.event == HookEvent.SESSION_START
        assert ctx.data == {}
        assert ctx.cancel is False

    def test_context_with_data(self):
        ctx = HookContext(
            event=HookEvent.SESSION_END,
            data={"key": "value"},
            cancel=True,
        )
        assert ctx.data["key"] == "value"
        assert ctx.cancel is True


class TestHookRegistry:
    def test_create_empty_registry(self):
        registry = HookRegistry()
        assert not registry.has_hooks(HookEvent.SESSION_START)
        assert registry.handler_count(HookEvent.SESSION_START) == 0

    def test_register_handler(self):
        registry = HookRegistry()

        async def handler(ctx: HookContext) -> None:
            pass

        registry.register(HookEvent.SESSION_START, handler)
        assert registry.has_hooks(HookEvent.SESSION_START)
        assert registry.handler_count(HookEvent.SESSION_START) == 1

    def test_register_multiple_handlers(self):
        registry = HookRegistry()

        async def handler1(ctx: HookContext) -> None:
            pass

        async def handler2(ctx: HookContext) -> None:
            pass

        registry.register(HookEvent.SESSION_START, handler1)
        registry.register(HookEvent.SESSION_START, handler2)
        assert registry.handler_count(HookEvent.SESSION_START) == 2

    def test_register_different_events(self):
        registry = HookRegistry()

        async def start_handler(ctx: HookContext) -> None:
            pass

        async def end_handler(ctx: HookContext) -> None:
            pass

        registry.register(HookEvent.SESSION_START, start_handler)
        registry.register(HookEvent.SESSION_END, end_handler)
        assert registry.has_hooks(HookEvent.SESSION_START)
        assert registry.has_hooks(HookEvent.SESSION_END)
        assert not registry.has_hooks(HookEvent.BEFORE_EXECUTE)

    def test_unregister_handler(self):
        registry = HookRegistry()

        async def handler(ctx: HookContext) -> None:
            pass

        registry.register(HookEvent.SESSION_START, handler)
        assert registry.has_hooks(HookEvent.SESSION_START)

        registry.unregister(HookEvent.SESSION_START, handler)
        assert not registry.has_hooks(HookEvent.SESSION_START)

    def test_clear_all_hooks(self):
        registry = HookRegistry()

        async def h1(ctx: HookContext) -> None:
            pass

        async def h2(ctx: HookContext) -> None:
            pass

        registry.register(HookEvent.SESSION_START, h1)
        registry.register(HookEvent.SESSION_END, h2)
        assert registry.has_hooks(HookEvent.SESSION_START)
        assert registry.has_hooks(HookEvent.SESSION_END)

        registry.clear()
        assert not registry.has_hooks(HookEvent.SESSION_START)
        assert not registry.has_hooks(HookEvent.SESSION_END)

    def test_clear_specific_event(self):
        registry = HookRegistry()

        async def h1(ctx: HookContext) -> None:
            pass

        async def h2(ctx: HookContext) -> None:
            pass

        registry.register(HookEvent.SESSION_START, h1)
        registry.register(HookEvent.SESSION_END, h2)

        registry.clear(HookEvent.SESSION_START)
        assert not registry.has_hooks(HookEvent.SESSION_START)
        assert registry.has_hooks(HookEvent.SESSION_END)


class TestHookFiring:
    @pytest.mark.asyncio
    async def test_fire_no_handlers(self):
        registry = HookRegistry()
        ctx = await registry.fire(HookEvent.SESSION_START)
        assert ctx.event == HookEvent.SESSION_START
        assert ctx.data == {}
        assert ctx.cancel is False

    @pytest.mark.asyncio
    async def test_fire_calls_handler(self):
        registry = HookRegistry()
        called = []

        async def handler(ctx: HookContext) -> None:
            called.append(True)

        registry.register(HookEvent.SESSION_START, handler)
        ctx = await registry.fire(HookEvent.SESSION_START)
        assert len(called) == 1
        assert ctx.event == HookEvent.SESSION_START

    @pytest.mark.asyncio
    async def test_fire_calls_multiple_handlers_in_order(self):
        registry = HookRegistry()
        order = []

        async def handler1(ctx: HookContext) -> None:
            order.append(1)

        async def handler2(ctx: HookContext) -> None:
            order.append(2)

        registry.register(HookEvent.SESSION_START, handler1)
        registry.register(HookEvent.SESSION_START, handler2)
        await registry.fire(HookEvent.SESSION_START)
        assert order == [1, 2]

    @pytest.mark.asyncio
    async def test_fire_mutates_context(self):
        registry = HookRegistry()

        async def handler(ctx: HookContext) -> None:
            ctx.data["mutated"] = True

        registry.register(HookEvent.SESSION_START, handler)
        ctx = await registry.fire(HookEvent.SESSION_START)
        assert ctx.data["mutated"] is True

    @pytest.mark.asyncio
    async def test_fire_cancel_stops_iteration(self):
        registry = HookRegistry()
        order = []

        async def handler1(ctx: HookContext) -> None:
            order.append(1)
            ctx.cancel = True

        async def handler2(ctx: HookContext) -> None:
            order.append(2)

        registry.register(HookEvent.SESSION_START, handler1)
        registry.register(HookEvent.SESSION_START, handler2)
        ctx = await registry.fire(HookEvent.SESSION_START)
        assert order == [1]
        assert ctx.cancel is True

    @pytest.mark.asyncio
    async def test_fire_handler_exception_does_not_stop_others(self):
        registry = HookRegistry()
        order = []

        async def bad_handler(ctx: HookContext) -> None:
            raise ValueError("boom")

        async def good_handler(ctx: HookContext) -> None:
            order.append("good")

        registry.register(HookEvent.SESSION_START, bad_handler)
        registry.register(HookEvent.SESSION_START, good_handler)
        ctx = await registry.fire(HookEvent.SESSION_START)
        assert order == ["good"]

    @pytest.mark.asyncio
    async def test_fire_with_prebuilt_context(self):
        registry = HookRegistry()
        received = []

        async def handler(ctx: HookContext) -> None:
            received.append(ctx.data.get("key"))

        registry.register(HookEvent.SESSION_START, handler)
        prebuilt = HookContext(
            event=HookEvent.SESSION_START,
            data={"key": "custom_value"},
        )
        ctx = await registry.fire(HookEvent.SESSION_START, prebuilt)
        assert received == ["custom_value"]
        assert ctx is prebuilt

    @pytest.mark.asyncio
    async def test_fire_only_fires_for_matching_event(self):
        registry = HookRegistry()
        called = []

        async def handler(ctx: HookContext) -> None:
            called.append(True)

        registry.register(HookEvent.SESSION_START, handler)
        await registry.fire(HookEvent.SESSION_END)
        assert len(called) == 0


class TestHookIntegration:
    @pytest.mark.asyncio
    async def test_engine_has_hooks_attribute(self):
        from sharp import HarnessEngine

        engine = HarnessEngine()
        assert hasattr(engine, "hooks")
        assert isinstance(engine.hooks, HookRegistry)

    @pytest.mark.asyncio
    async def test_engine_hooks_fire_on_run(self):
        from sharp import HarnessEngine

        engine = HarnessEngine()
        events_fired = []

        async def track_events(ctx: HookContext) -> None:
            events_fired.append(ctx.event.value)

        engine.hooks.register(HookEvent.SESSION_START, track_events)
        engine.hooks.register(HookEvent.SESSION_END, track_events)

        result = await engine.run("test request")
        assert "session_start" in events_fired
        assert "session_end" in events_fired
