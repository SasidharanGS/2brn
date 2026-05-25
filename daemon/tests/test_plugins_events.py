import pytest

from brn_daemon.plugins.events import EventBus, EventNames


async def test_subscribe_and_emit_delivers_payload():
    bus = EventBus()
    seen: list[tuple[str, dict]] = []

    async def handler(name: str, payload: dict) -> None:
        seen.append((name, payload))

    bus.subscribe(EventNames.JOURNAL_GENERATED, handler)
    await bus.emit(EventNames.JOURNAL_GENERATED, {"date": "2026-05-23", "content": "hi"})
    assert seen == [("journal_generated", {"date": "2026-05-23", "content": "hi"})]


async def test_emit_with_no_subscribers_is_noop():
    bus = EventBus()
    await bus.emit(EventNames.CAPTURE_INFERRED, {"summary": "x"})


async def test_handler_exception_does_not_block_other_handlers():
    bus = EventBus()
    calls: list[str] = []

    async def bad(_n, _p):
        calls.append("bad")
        raise RuntimeError("boom")

    async def good(_n, _p):
        calls.append("good")

    bus.subscribe(EventNames.BLOG_GENERATED, bad)
    bus.subscribe(EventNames.BLOG_GENERATED, good)
    await bus.emit(EventNames.BLOG_GENERATED, {})
    assert sorted(calls) == ["bad", "good"]


async def test_unsubscribe_removes_handler():
    bus = EventBus()
    seen: list[str] = []

    async def h(_n, _p):
        seen.append("fired")

    bus.subscribe(EventNames.JOURNAL_GENERATED, h)
    bus.unsubscribe(EventNames.JOURNAL_GENERATED, h)
    await bus.emit(EventNames.JOURNAL_GENERATED, {})
    assert seen == []
