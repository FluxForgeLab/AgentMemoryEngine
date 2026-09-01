from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

@dataclass(frozen=True)
class MultimodalInput:
    texts: tuple[str, ...] = ()
    images: tuple[str, ...] = ()
    videos: tuple[str, ...] = ()

    @classmethod
    def text(cls, text: str) -> "MultimodalInput":
        text = text.strip()
        if not text:
            raise ValueError("text cannot be empty")
        return cls(texts=(text,))

    @classmethod
    def mixed(cls, *, texts=(), images=(), videos=()) -> "MultimodalInput":
        obj = cls(
            texts=tuple(x.strip() for x in texts if x and x.strip()),
            images=tuple(x.strip() for x in images if x and x.strip()),
            videos=tuple(x.strip() for x in videos if x and x.strip()),
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        if not (self.texts or self.images or self.videos):
            raise ValueError("MultimodalInput cannot be empty")

    def searchable_text(self) -> str:
        return "\n".join(self.texts).strip()

    def modality(self) -> str:
        kinds = [bool(self.texts), bool(self.images), bool(self.videos)]
        if sum(kinds) > 1:
            return "mixed"
        if self.images:
            return "image"
        if self.videos:
            return "video"
        return "text"

@dataclass(frozen=True)
class EmbeddingDescriptor:
    provider: str
    model: str
    dimension: int
    normalized: bool
    space_id: str

@dataclass
class MemoryRecord:
    id: str
    content: MultimodalInput
    importance: float = 0.5
    source_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, content: MultimodalInput, *, importance=0.5,
               source_uri=None, metadata=None) -> "MemoryRecord":
        content.validate()
        importance = float(importance)
        if not 0 <= importance <= 1:
            raise ValueError("importance must be between 0 and 1")
        return cls(
            id=str(uuid4()),
            content=content,
            importance=importance,
            source_uri=source_uri,
            metadata=dict(metadata or {}),
        )

@dataclass(frozen=True)
class RerankCandidate:
    id: str
    content: MultimodalInput
    retrieval_score: float
    importance: float = 0.5
    created_at: datetime | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def provider_primary_view(self) -> tuple[str, str]:
        # 百炼 qwen3-vl-rerank 当前每个 candidate 是 text/image/video 之一。
        if self.content.images:
            return "image", self.content.images[0]
        if self.content.videos:
            return "video", self.content.videos[0]
        if self.content.texts:
            return "text", self.content.searchable_text()
        raise ValueError("empty candidate")

@dataclass(frozen=True)
class RerankResult:
    candidate: RerankCandidate
    rerank_score: float
    rank: int
