from __future__ import annotations

from typing import Protocol, Sequence

from .domain import (
    EmbeddingDescriptor,
    MultimodalInput,
    RerankCandidate,
    RerankResult,
)


class EmbeddingAdapter(Protocol):
    @property
    def descriptor(self) -> EmbeddingDescriptor: ...

    def embed(
        self,
        content: MultimodalInput,
        *,
        instruct: str | None = None,
    ) -> list[float]: ...


class RerankerAdapter(Protocol):
    def rerank(
        self,
        query: MultimodalInput,
        candidates: Sequence[RerankCandidate],
        *,
        top_k: int | None = None,
        instruct: str | None = None,
    ) -> list[RerankResult]: ...


class MemoryRepository(Protocol):
    def vector_search(
        self,
        query: MultimodalInput,
        *,
        top_k: int = 40,
    ) -> Sequence[RerankCandidate]: ...

    def keyword_search(
        self,
        query_text: str,
        *,
        top_k: int = 40,
    ) -> Sequence[RerankCandidate]: ...
