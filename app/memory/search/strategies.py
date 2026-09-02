from __future__ import annotations

from typing import Any

from app.domain.interfaces import EmbeddingProvider, MemoryRepository
from app.domain.models import MemoryType
from app.memory.search.fusion import reciprocal_rank_fusion
from app.observability.trace import emit


class KeywordSearchStrategy:
    def __init__(self, repository: MemoryRepository):
        self.repository = repository

    async def search(self, *, query: str, top_k: int, memory_types, filters):
        results = await self.repository.keyword_search(
            query,
            limit=top_k,
            memory_types=memory_types,
            filters=filters,
        )
        for item in results:
            item["score"] = float(item.get("keyword_score", 0.0))
            item["route"] = "keyword"
        emit("search.keyword", query=query, hits=len(results), top_k=top_k)
        return results


class VectorSearchStrategy:
    def __init__(self, repository: MemoryRepository, embedder: EmbeddingProvider):
        self.repository = repository
        self.embedder = embedder

    async def search(self, *, query: str, top_k: int, memory_types, filters):
        vector = await self.embedder.embed(query)
        results = await self.repository.vector_search(
            vector,
            limit=top_k,
            memory_types=memory_types,
            filters=filters,
        )
        for item in results:
            item["score"] = float(item.get("vector_score", 0.0))
            item["route"] = "vector"
        emit("search.vector", query=query, hits=len(results), top_k=top_k)
        return results


class HybridSearchStrategy:
    def __init__(
        self,
        repository: MemoryRepository,
        embedder: EmbeddingProvider,
        *,
        variant: str = "standard",
    ):
        self.keyword = KeywordSearchStrategy(repository)
        self.vector = VectorSearchStrategy(repository, embedder)
        self.variant = variant

    async def search(self, *, query: str, top_k: int, memory_types, filters):
        candidate_k = max(top_k * 4, 20)
        keyword_results = await self.keyword.search(
            query=query,
            top_k=candidate_k,
            memory_types=memory_types,
            filters=filters,
        )
        vector_results = await self.vector.search(
            query=query,
            top_k=candidate_k,
            memory_types=memory_types,
            filters=filters,
        )

        if self.variant == "vector_anchored":
            # Reflection / Experience：语义经验优先，关键词补充。
            fused = reciprocal_rank_fusion(
                [vector_results, vector_results, keyword_results]
            )
        elif self.variant == "skill_hybrid":
            # Procedural：术语精确度和语义同等重要。
            fused = reciprocal_rank_fusion([keyword_results, vector_results])
        else:
            fused = reciprocal_rank_fusion([vector_results, keyword_results])

        for item in fused:
            item["route"] = f"hybrid:{self.variant}"
        trimmed = fused[:top_k]
        emit(
            "search.hybrid",
            variant=self.variant,
            keyword_hits=len(keyword_results),
            vector_hits=len(vector_results),
            fused=len(fused),
            hits=len(trimmed),
        )
        return trimmed
