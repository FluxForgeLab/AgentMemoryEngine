from __future__ import annotations

from contextvars import ContextVar

source_var: ContextVar[str] = ContextVar("ame_source", default="unknown")
session_var: ContextVar[str] = ContextVar("ame_session", default="")
turn_var: ContextVar[str] = ContextVar("ame_turn", default="orphan")
span_var: ContextVar[str] = ContextVar("ame_span", default="")
