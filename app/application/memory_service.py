from __future__ import annotations

from typing import Any

from app.application.memory_manager import MemoryManager
from app.domain.models import Memory, MemoryType, SearchMethod
from app.memory.search.router import SearchRouter


class MemoryService:
    """Application layer：CRUD 与 SearchRouter 的稳定入口。"""

    def __init__(
        self,
        manager: MemoryManager,
        search_router: SearchRouter,
    ):
        self.manager = manager
        self.search_router = search_router

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
        method: SearchMethod,
        top_k: int,
        memory_types: list[MemoryType] | None,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return await self.search_router.search(
            query=query,
            method=method,
            top_k=top_k,
            memory_types=memory_types,
            filters=filters,
        )

    async def get_memory(self, memory_id: str) -> Memory | None:
        return await self.manager.get(memory_id)

    async def delete_memory(self, memory_id: str) -> bool:
        return await self.manager.delete(memory_id)

    async def update_memory(self, memory_id: str, **updates) -> Memory | None:
        return await self.manager.update(memory_id, **updates)
