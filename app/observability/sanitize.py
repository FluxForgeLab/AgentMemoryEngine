from __future__ import annotations

from typing import Any

_SECRET_KEYS = {
    "api_key",
    "authorization",
    "llm_api_key",
    "dashscope_api_key",
    "password",
    "secret",
    "token",
    "bearer",
}

_DROP_KEYS = {"vector", "embedding"}

_FULL_KEYS = {
    "memory_context",
    "messages",
    "answer",
    "answer_without_memory",
}

_DEFAULT_CLIP = 500
_FULL_CLIP = 32_768


def clip_text(value: Any, limit: int = _DEFAULT_CLIP) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[:limit] + f"...<truncated:{len(value) - limit}>"


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _sanitize(payload)  # type: ignore[return-value]


def _sanitize(value: Any, *, key: str = "") -> Any:
    lowered = key.lower()
    if lowered in _SECRET_KEYS or any(part in lowered for part in ("api_key", "authorization")):
        return "<redacted>"
    if lowered in _DROP_KEYS:
        if isinstance(value, list):
            return f"<omitted:{len(value)}>"
        return "<omitted>"

    if isinstance(value, dict):
        return {str(k): _sanitize(v, key=str(k)) for k, v in value.items()}

    if isinstance(value, list):
        if value and all(isinstance(x, (int, float)) for x in value[:8]) and len(value) > 16:
            return f"<omitted:{len(value)}>"
        if len(value) > 50:
            return [_sanitize(x) for x in value[:50]] + [f"<truncated:{len(value) - 50}>"]
        return [_sanitize(x) for x in value]

    if isinstance(value, str):
        limit = _FULL_CLIP if lowered in _FULL_KEYS else _DEFAULT_CLIP
        return clip_text(value, limit)

    return value
