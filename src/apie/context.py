from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Callable, Optional, TypeVar

T = TypeVar("T")

_run_id: ContextVar[Optional[str]] = ContextVar("apie_run_id", default=None)
_session_id: ContextVar[Optional[str]] = ContextVar("apie_session_id", default=None)


def get_run_context() -> dict[str, Optional[str]]:
    return {"runId": _run_id.get(), "sessionId": _session_id.get()}


def resolve_run_id(explicit: Optional[str] = None) -> Optional[str]:
    return explicit or _run_id.get()


def resolve_session_id(explicit: Optional[str] = None) -> Optional[str]:
    return explicit or _session_id.get()


def run_context(
    *,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Callable[[Callable[[], T]], Callable[[], T]]:
    def decorator(fn: Callable[[], T]) -> Callable[[], T]:
        def wrapper() -> T:
            tokens: list[Token[Optional[str]]] = []
            if run_id is not None:
                tokens.append(_run_id.set(run_id))
            if session_id is not None:
                tokens.append(_session_id.set(session_id))
            try:
                return fn()
            finally:
                for token in reversed(tokens):
                    token.var.reset(token)

        return wrapper

    return decorator
