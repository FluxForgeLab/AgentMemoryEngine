from __future__ import annotations

from typing import Any

from app.application.memory_manager import MemoryManager
from app.domain.models import Memory, MemoryType
from app.retrieval.pipeline import RetrievalPipeline


class MemoryService:
    """Application layer: orchestrates complete memory use cases."""

    def __init__(
        self,
        manager: MemoryManager,
        retriever: RetrievalPipeline,
    ):
        self.manager = manager
        self.retriever = retriever

    async def store_memory(
        self,
        *,
        content: str,
        memory_type: MemoryType,
        importance: float,
        metadata: dict[str, Any],
    ) -> Memory:
        return await self.manager.store(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )

    async def search_memory(
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
        return await self.retriever.search(
            query=query,
            top_k=top_k,
            memory_types=memory_types,
            filters=filters,
            use_vector=use_vector,
            use_keyword=use_keyword,
            rerank=rerank,
        )

    async def get_memory(self, memory_id: str) -> Memory | None:
        return await self.manager.get(memory_id)

    async def delete_memory(self, memory_id: str) -> bool:
        return await self.manager.delete(memory_id)

    async def update_memory(self, memory_id: str, **updates) -> Memory | None:
        return await self.manager.update(memory_id, **updates)
