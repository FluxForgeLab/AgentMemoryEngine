from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator
from uuid import uuid4

from app.observability import context as ctx
from app.observability.sanitize import sanitize_payload
from app.observability.sink import NullSink, now_iso

_sink: Any = NullSink()


def set_sink(sink: Any) -> None:
    global _sink
    _sink = sink


def current_sink() -> Any:
    return _sink


def bind_session(*, source: str, session_id: str) -> None:
    ctx.source_var.set(source)
    ctx.session_var.set(session_id)


def bind_turn(turn_id: str | None = None) -> str:
    value = turn_id or uuid4().hex[:8]
    ctx.turn_var.set(value)
    return value


def reset_context() -> None:
    ctx.turn_var.set("orphan")
    ctx.span_var.set("")


def emit(event: str, **payload: Any) -> None:
    sink = _sink
    if sink is None or getattr(sink, "disabled", False):
        return

    record = {
        "ts": now_iso(),
        "source": ctx.source_var.get(),
        "session": ctx.session_var.get(),
        "turn": ctx.turn_var.get() or "orphan",
        "span": ctx.span_var.get(),
        "event": event,
        "payload": sanitize_payload(payload),
    }
    if "elapsed_ms" in payload:
        record["elapsed_ms"] = payload["elapsed_ms"]
    sink.write(record)


@contextmanager
def span(name: str) -> Iterator[None]:
    previous = ctx.span_var.get()
    ctx.span_var.set(name)
    started = time.perf_counter()
    emit(f"{name}.start")
    try:
        yield
    except Exception as exc:
        emit(
            f"{name}.error",
            error_type=type(exc).__name__,
            elapsed_ms=_ms(started),
        )
        raise
    else:
        emit(f"{name}.end", elapsed_ms=_ms(started))
    finally:
        ctx.span_var.set(previous)


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
