from __future__ import annotations

from typing import Any

from app.application.memory_manager import MemoryManager
from app.domain.models import Memory, MemoryType, SearchMethod
from app.memory.search.router import SearchRouter
from app.observability.trace import emit, span


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
        with span("service.store"):
            memory = await self.manager.store(
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
            )
            emit(
                "memory.store.end",
                id=memory.id,
                memory_type=memory.memory_type.value,
                importance=memory.importance,
            )
            return memory

    async def search_memory(
        self,
        *,
        query: str,
        method: SearchMethod,
        top_k: int,
        memory_types: list[MemoryType] | None,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        with span("service.search"):
            results = await self.search_router.search(
                query=query,
                method=method,
                top_k=top_k,
                memory_types=memory_types,
                filters=filters,
            )
            emit(
                "service.search",
                query=query,
                method=method.value,
                top_k=top_k,
                memory_types=[x.value for x in memory_types] if memory_types else None,
                filters=filters,
                hits=len(results),
            )
            return results

    async def get_memory(self, memory_id: str) -> Memory | None:
        memory = await self.manager.get(memory_id)
        emit("memory.get", id=memory_id, found=memory is not None)
        return memory

    async def delete_memory(self, memory_id: str) -> bool:
        deleted = await self.manager.delete(memory_id)
        emit("memory.delete", id=memory_id, deleted=deleted)
        return deleted

    async def update_memory(self, memory_id: str, **updates) -> Memory | None:
        memory = await self.manager.update(memory_id, **updates)
        emit(
            "memory.update",
            id=memory_id,
            found=memory is not None,
            fields=list(updates.keys()),
        )
        return memory
