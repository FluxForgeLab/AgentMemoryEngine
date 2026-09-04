from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.api.dependencies import get_memory_service
from app.config import get_settings
from memory_engine.providers.bailian import BailianConfig


@dataclass
class Readiness:
    ready: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def live_payload() -> dict[str, Any]:
    return {"status": "ok", "stage": 10, "check": "live"}


def legacy_health_payload() -> dict[str, Any]:
    return {"status": "ok", "stage": 10}


def embedding_is_configured() -> tuple[bool, str]:
    settings = get_settings()
    provider = settings.embedding_provider.lower()

    if provider == "mock":
        return True, "mock"

    if provider == "qwen":
        try:
            BailianConfig.from_env()
        except Exception as exc:
            return False, str(exc)
        return True, "qwen"

    return False, f"unsupported embedding provider: {provider}"


def _dir_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ame_ready"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def assess_readiness() -> Readiness:
    configured, embedding = embedding_is_configured()
    if not configured:
        return Readiness(
            False,
            embedding,
            {"embedding": "not_configured"},
        )

    try:
        service = get_memory_service()
    except Exception as exc:
        return Readiness(
            False,
            f"memory service init failed: {exc}",
            {"service": "unavailable"},
        )

    settings = get_settings()
    db_path = Path(settings.memory_db_path)
    if not _dir_is_writable(db_path):
        return Readiness(
            False,
            f"LanceDB directory not writable: {db_path}",
            {"storage": "not_writable"},
        )

    table = getattr(service.manager.repository, "table", None)
    if table is None:
        return Readiness(
            False,
            "LanceDB table is not open",
            {"storage": "table_closed"},
        )

    try:
        _ = table.schema
    except Exception as exc:
        return Readiness(
            False,
            f"LanceDB table is not usable: {exc}",
            {"storage": "table_error"},
        )

    return Readiness(
        True,
        None,
        {
            "service": "initialized",
            "storage": "writable",
            "embedding": embedding,
        },
    )


def readiness_body(result: Readiness) -> dict[str, Any]:
    body = {
        "status": "ok" if result.ready else "not_ready",
        "stage": 10,
        "check": "ready",
        **result.details,
    }
    if result.reason:
        body["reason"] = result.reason
    return body
