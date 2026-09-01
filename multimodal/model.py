from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .types import Modality


@dataclass(frozen=True)
class ArtifactChunk:
    """
    Text / Code / Document / Log 的统一 Chunk。

    Stage 8 的关键思想：
        Raw Object != Search Record

    Processor 先把原始对象转换成可检索的 Chunk，
    Repository 再为 Chunk 生成 vector 并落库。
    """

    id: str
    modality: Modality
    content: str

    source_uri: str | None = None
    source_type: str | None = None

    language: str | None = None
    symbol: str | None = None
    symbol_type: str | None = None

    page: int | None = None
    chunk_index: int = 0

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def create(
        cls,
        *,
        modality: Modality | str,
        content: str,
        source_uri: str | None = None,
        source_type: str | None = None,
        language: str | None = None,
        symbol: str | None = None,
        symbol_type: str | None = None,
        page: int | None = None,
        chunk_index: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "ArtifactChunk":
        content = _require_text(content, "content")

        return cls(
            id=str(uuid4()),
            modality=Modality(modality),
            content=content,
            source_uri=source_uri,
            source_type=source_type,
            language=language,
            symbol=symbol,
            symbol_type=symbol_type,
            page=page,
            chunk_index=chunk_index,
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class ImageMemory:
    id: str
    uri: str
    caption: str
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def create(
        cls,
        *,
        uri: str,
        caption: str = "",
        width: int | None = None,
        height: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageMemory":
        uri = _require_text(uri, "uri")
        return cls(
            id=str(uuid4()),
            uri=uri,
            caption=caption.strip(),
            width=width,
            height=height,
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class RetrievalPlan:
    """
    Query Router 的输出。

    注意：
        Router 不需要自由生成任意浮点参数。
        当前使用有限的 heuristic profile，
        后续可以由 Evaluation / Experience Loop 调整。
    """

    artifact_modalities: tuple[Modality, ...]
    search_images: bool
    search_legacy_memory: bool

    artifact_mode: str = "hybrid"

    legacy_weight: float = 1.0
    artifact_weight: float = 1.0
    image_weight: float = 1.0

    candidate_k: int = 20


@dataclass(frozen=True)
class UnifiedResult:
    id: str
    source: str
    modality: Modality
    content: str

    uri: str | None = None
    score: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")

    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty")

    return value
