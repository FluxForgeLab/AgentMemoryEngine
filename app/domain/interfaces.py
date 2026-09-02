from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.domain.models import Memory, MemoryType


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class MemoryRepository(ABC):
    @abstractmethod
    async def add(self, memory: Memory) -> Memory:
        raise NotImplementedError

    @abstractmethod
    async def get(self, memory_id: str) -> Memory | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def update(
        self,
        memory_id: str,
        updates: dict[str, Any],
    ) -> Memory | None:
        raise NotImplementedError

    @abstractmethod
    async def vector_search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        memory_types: list[MemoryType] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def keyword_search(
        self,
        query: str,
        *,
        limit: int,
        memory_types: list[MemoryType] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError
