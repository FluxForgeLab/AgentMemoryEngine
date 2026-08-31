from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from lancedb.table import Table

from embedding.embedder import TextEmbedder
from hybrid.types import SearchMode

from .retriever import MemoryRetriever
from .scorer import MemoryScorer


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    REFLECTION = "reflection"


class MemoryManager:
    """
    第七阶段 MemoryManager。

    生命周期能力仍然不变：
        store / search / update / delete

    变化只发生在 search：
        mode = vector / keyword / hybrid
    """

    def __init__(
        self,
        table: Table,
        embedder: TextEmbedder,
        *,
        scorer: MemoryScorer | None = None,
    ) -> None:
        self.table = table
        self.embedder = embedder
        self.scorer = scorer or MemoryScorer()

        self.retriever = MemoryRetriever(
            table=table,
            embedder=embedder,
            scorer=self.scorer,
        )

    def store(
        self,
        content: str,
        *,
        memory_type: MemoryType | str,
        importance: float = 0.5,
    ) -> str:
        content = self._validate_content(
            content
        )

        normalized_type = (
            self._normalize_memory_type(
                memory_type
            )
        )

        importance = (
            self._validate_importance(
                importance
            )
        )

        memory_id = str(
            uuid4()
        )

        self.table.add(
            [
                {
                    "id": memory_id,
                    "content": content,
                    "vector": self.embedder.encode(
                        content
                    ),
                    "type": normalized_type,
                    "importance": importance,
                    "created_at": datetime.now(
                        timezone.utc
                    ),
                }
            ]
        )

        return memory_id

    def search(
        self,
        query: str,
        *,
        mode: SearchMode | str = SearchMode.HYBRID,
        memory_types: Sequence[MemoryType | str] | None = None,
        min_importance: float | None = None,
        top_k: int = 5,
        candidate_k: int | None = None,
        extra_filter: str | None = None,
        rerank: bool | None = None,
        rerank_memory: bool = True,
    ) -> list[dict[str, Any]]:
        normalized_types = None

        if memory_types is not None:
            normalized_types = [
                self._normalize_memory_type(
                    value
                )
                for value in memory_types
            ]

        return self.retriever.search(
            query,
            mode=mode,
            memory_types=normalized_types,
            min_importance=min_importance,
            top_k=top_k,
            candidate_k=candidate_k,
            extra_filter=extra_filter,
            rerank=rerank,
            rerank_memory=rerank_memory,
        )

    def get(
        self,
        memory_id: str,
    ) -> dict[str, Any] | None:
        return self.retriever.get_by_id(
            memory_id
        )

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        memory_type: MemoryType | str | None = None,
        importance: float | None = None,
    ) -> bool:
        memory_id = self._validate_memory_id(
            memory_id
        )

        values: dict[str, Any] = {}

        if content is not None:
            content = self._validate_content(
                content
            )

            values["content"] = content

            # 保持核心数据不变量：
            # vector = Embedding(content)
            values["vector"] = self.embedder.encode(
                content
            )

        if memory_type is not None:
            values["type"] = (
                self._normalize_memory_type(
                    memory_type
                )
            )

        if importance is not None:
            values["importance"] = (
                self._validate_importance(
                    importance
                )
            )

        if not values:
            return False

        result = self.table.update(
            where=(
                f"id = "
                f"{self._sql_string(memory_id)}"
            ),
            values=values,
        )

        rows_updated = getattr(
            result,
            "rows_updated",
            None,
        )

        return (
            True
            if rows_updated is None
            else rows_updated > 0
        )

    def delete(
        self,
        memory_id: str,
    ) -> bool:
        memory_id = self._validate_memory_id(
            memory_id
        )

        result = self.table.delete(
            f"id = {self._sql_string(memory_id)}"
        )

        count = getattr(
            result,
            "num_deleted_rows",
            None,
        )

        return (
            True
            if count is None
            else count > 0
        )

    @staticmethod
    def _validate_content(
        content: str,
    ) -> str:
        if not isinstance(content, str):
            raise TypeError(
                "content must be a string"
            )

        content = content.strip()

        if not content:
            raise ValueError(
                "content cannot be empty"
            )

        return content

    @staticmethod
    def _validate_memory_id(
        memory_id: str,
    ) -> str:
        if not isinstance(memory_id, str):
            raise TypeError(
                "memory_id must be a string"
            )

        memory_id = memory_id.strip()

        if not memory_id:
            raise ValueError(
                "memory_id cannot be empty"
            )

        return memory_id

    @staticmethod
    def _validate_importance(
        importance: float,
    ) -> float:
        importance = float(
            importance
        )

        if not 0.0 <= importance <= 1.0:
            raise ValueError(
                "importance must be between 0 and 1"
            )

        return importance

    @staticmethod
    def _normalize_memory_type(
        memory_type: MemoryType | str,
    ) -> str:
        if isinstance(
            memory_type,
            MemoryType,
        ):
            return memory_type.value

        if not isinstance(
            memory_type,
            str,
        ):
            raise TypeError(
                "memory_type must be MemoryType or str"
            )

        value = memory_type.strip().lower()

        try:
            return MemoryType(value).value

        except ValueError as exc:
            allowed = ", ".join(
                item.value
                for item in MemoryType
            )

            raise ValueError(
                f"invalid memory type: {value}. "
                f"allowed: {allowed}"
            ) from exc

    @staticmethod
    def _sql_string(
        value: str,
    ) -> str:
        escaped = value.replace(
            "'",
            "''",
        )
        return f"'{escaped}'"
