from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Sequence

from app.domain.interfaces import MemoryRepository
from app.domain.models import Memory, MemoryType
from storage import open_service_memories_table


class LanceDBMemoryRepository(MemoryRepository):
    def __init__(
        self,
        db_path: str,
        table_name: str,
        embedding_dim: int,
    ):
        self.db_path = db_path
        self.table_name = table_name
        self.embedding_dim = embedding_dim
        self.table = open_service_memories_table(
            dimension=embedding_dim,
            db_path=db_path,
            table_name=table_name,
        )
        _ensure_vector_dimension(self.table, embedding_dim)

    @staticmethod
    def _to_row(memory: Memory) -> dict[str, Any]:
        return {
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "importance": memory.importance,
            "metadata_json": json.dumps(memory.metadata, ensure_ascii=False),
            "vector": memory.vector,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: dict[str, Any]) -> Memory:
        return Memory(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            importance=float(row["importance"]),
            metadata=json.loads(row.get("metadata_json") or "{}"),
            vector=list(row["vector"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    async def add(self, memory: Memory) -> Memory:
        await asyncio.to_thread(self.table.add, [self._to_row(memory)])
        return memory

    async def get(self, memory_id: str) -> Memory | None:
        def _get():
            rows = (
                self.table.search()
                .where(f"id = {_sql(memory_id)}")
                .limit(1)
                .to_list()
            )
            return rows[0] if rows else None

        row = await asyncio.to_thread(_get)
        return self._from_row(row) if row else None

    async def delete(self, memory_id: str) -> bool:
        existing = await self.get(memory_id)
        if not existing:
            return False

        await asyncio.to_thread(
            self.table.delete,
            f"id = {_sql(memory_id)}",
        )
        return True

    async def update(
        self,
        memory_id: str,
        updates: dict[str, Any],
    ) -> Memory | None:
        memory = await self.get(memory_id)
        if not memory:
            return None

        data = memory.model_dump()
        data.update(updates)
        updated = Memory(**data)

        await asyncio.to_thread(
            self.table.delete,
            f"id = {_sql(memory_id)}",
        )
        await asyncio.to_thread(self.table.add, [self._to_row(updated)])
        return updated

    @staticmethod
    def _passes_filters(
        row: dict[str, Any],
        memory_types: list[MemoryType] | None,
        filters: dict[str, Any] | None,
    ) -> bool:
        if memory_types:
            allowed = {x.value for x in memory_types}
            if row["memory_type"] not in allowed:
                return False

        if filters:
            metadata = json.loads(row.get("metadata_json") or "{}")
            for key, expected in filters.items():
                if metadata.get(key) != expected:
                    return False

        return True

    async def vector_search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        memory_types: list[MemoryType] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if _is_empty_table(self.table):
            return []

        fetch_limit = max(limit * 4, limit)

        def _search():
            return (
                self.table.search(
                    list(vector),
                    query_type="vector",
                    vector_column_name="vector",
                )
                .distance_type("cosine")
                .limit(fetch_limit)
                .to_list()
            )

        rows = await asyncio.to_thread(_search)

        output = []
        for row in rows:
            if not self._passes_filters(row, memory_types, filters):
                continue

            distance = float(row.get("_distance", 0.0))
            score = 1.0 / (1.0 + max(distance, 0.0))

            output.append({
                "id": row["id"],
                "content": row["content"],
                "memory_type": row["memory_type"],
                "importance": float(row["importance"]),
                "metadata": json.loads(row.get("metadata_json") or "{}"),
                "vector_score": score,
            })

            if len(output) >= limit:
                break

        return output

    async def keyword_search(
        self,
        query: str,
        *,
        limit: int,
        memory_types: list[MemoryType] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if _is_empty_table(self.table):
            return []

        # Stage 10：database-agnostic 中文 2-gram lexical；不混入 Stage 5-8 的 FTS 空间。
        def _all_rows():
            return self.table.search().limit(10000).to_list()

        rows = await asyncio.to_thread(_all_rows)
        grams = _lexical_grams(query)

        scored = []
        for row in rows:
            if not self._passes_filters(row, memory_types, filters):
                continue

            content = "".join(row["content"].lower().split())
            if not grams:
                continue

            hits = sum(1 for gram in grams if gram in content)
            score = hits / len(grams)
            if score <= 0:
                continue

            scored.append({
                "id": row["id"],
                "content": row["content"],
                "memory_type": row["memory_type"],
                "importance": float(row["importance"]),
                "metadata": json.loads(row.get("metadata_json") or "{}"),
                "keyword_score": score,
            })

        scored.sort(key=lambda x: x["keyword_score"], reverse=True)
        return scored[:limit]


def _lexical_grams(query: str) -> set[str]:
    normalized = "".join(query.lower().split())
    return {
        normalized[i : i + 2]
        for i in range(max(0, len(normalized) - 1))
    }


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _is_empty_table(table: Any) -> bool:
    count_rows = getattr(table, "count_rows", None)
    return callable(count_rows) and count_rows() == 0


def _ensure_vector_dimension(table: Any, expected: int) -> None:
    if "vector" not in getattr(table.schema, "names", []):
        return
    list_size = getattr(table.schema.field("vector").type, "list_size", None)
    if list_size is not None and int(list_size) != int(expected):
        raise RuntimeError(
            f"vector dimension mismatch: table={list_size}, service={expected}"
        )
