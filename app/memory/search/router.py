from __future__ import annotations

from app.domain.interfaces import EmbeddingProvider, MemoryRepository
from app.domain.models import MemoryType, SearchMethod
from app.memory.search.agentic import AgenticSearchStrategy
from app.memory.search.strategies import (
    HybridSearchStrategy,
    KeywordSearchStrategy,
    VectorSearchStrategy,
)


class SearchRouter:
    """
    Memory Engine 内部 Router。

    不判断“要不要查 Memory”；只在已经决定检索后选择 pipeline。
    """

    def __init__(self, repository: MemoryRepository, embedder: EmbeddingProvider):
        self.repository = repository
        self.embedder = embedder
        self.keyword = KeywordSearchStrategy(repository)
        self.vector = VectorSearchStrategy(repository, embedder)
        self.agentic = AgenticSearchStrategy(repository, embedder)

    def _hybrid_variant(self, memory_types: list[MemoryType] | None) -> str:
        kinds = set(memory_types or [])
        if kinds & {MemoryType.experience, MemoryType.reflection}:
            return "vector_anchored"
        if kinds == {MemoryType.procedural}:
            return "skill_hybrid"
        return "standard"

    async def search(
        self,
        *,
        query: str,
        method: SearchMethod,
        top_k: int,
        memory_types: list[MemoryType] | None,
        filters: dict | None,
    ) -> list[dict]:
        kwargs = dict(
            query=query,
            top_k=top_k,
            memory_types=memory_types,
            filters=filters,
        )

        if method == SearchMethod.keyword:
            return await self.keyword.search(**kwargs)
        if method == SearchMethod.vector:
            return await self.vector.search(**kwargs)
        if method == SearchMethod.agentic:
            return await self.agentic.search(**kwargs)

        hybrid = HybridSearchStrategy(
            self.repository,
            self.embedder,
            variant=self._hybrid_variant(memory_types),
        )
        return await hybrid.search(**kwargs)
