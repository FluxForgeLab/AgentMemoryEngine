from __future__ import annotations

from typing import Any

from app.domain.interfaces import EmbeddingProvider, MemoryRepository, Reranker
from app.domain.models import MemoryType
from app.retrieval.fusion import reciprocal_rank_fusion


class RetrievalPipeline:
    def __init__(
        self,
        repository: MemoryRepository,
        embedder: EmbeddingProvider,
        reranker: Reranker,
    ):
        self.repository = repository
        self.embedder = embedder
        self.reranker = reranker

    async def search(
        self,
        *,
        query: str,
        top_k: int,
        memory_types: list[MemoryType] | None,
        filters: dict[str, Any] | None,
        use_vector: bool,
        use_keyword: bool,
        rerank: bool,
    ) -> list[dict[str, Any]]:
        candidate_limit = max(top_k * 4, 20)
        result_sets = []

        if use_vector:
            query_vector = await self.embedder.embed(query)
            vector_results = await self.repository.vector_search(
                query_vector,
                limit=candidate_limit,
                memory_types=memory_types,
                filters=filters,
            )
            result_sets.append(vector_results)

        if use_keyword:
            keyword_results = await self.repository.keyword_search(
                query,
                limit=candidate_limit,
                memory_types=memory_types,
                filters=filters,
            )
            result_sets.append(keyword_results)

        if not result_sets:
            return []

        candidates = reciprocal_rank_fusion(result_sets)

        if rerank:
            return await self.reranker.rerank(
                query,
                candidates,
                top_k,
            )

        return candidates[:top_k]
