from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.interfaces import EmbeddingProvider, MemoryRepository
from app.domain.models import Memory, MemoryType
from app.observability.trace import emit, span


class MemoryManager:
    def __init__(
        self,
        repository: MemoryRepository,
        embedder: EmbeddingProvider,
    ):
        self.repository = repository
        self.embedder = embedder

    async def store(
        self,
        *,
        content: str,
        memory_type: MemoryType,
        importance: float,
        metadata: dict[str, Any],
    ) -> Memory:
        with span("manager.store"):
            vector = await self.embedder.embed(content)
            memory = Memory.new(
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
                vector=vector,
            )
            stored = await self.repository.add(memory)
            emit(
                "memory.store.start",
                id=stored.id,
                memory_type=memory_type.value,
                content=content,
                reembedded=True,
            )
            return stored

    async def get(self, memory_id: str) -> Memory | None:
        return await self.repository.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        return await self.repository.delete(memory_id)

    async def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        memory_type: MemoryType | None = None,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory | None:
        current = await self.repository.get(memory_id)
        if not current:
            return None

        updates: dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc),
        }

        if content is not None:
            updates["content"] = content
            updates["vector"] = await self.embedder.embed(content)
            emit("memory.reembed", id=memory_id, content=content)

        if memory_type is not None:
            updates["memory_type"] = memory_type

        if importance is not None:
            updates["importance"] = importance

        if metadata is not None:
            updates["metadata"] = metadata

        return await self.repository.update(memory_id, updates)
