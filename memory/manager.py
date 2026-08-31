# memory/manager.py

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from lancedb.table import Table

from embedding.embedder import TextEmbedder

from .retriever import MemoryRetriever
from .scorer import MemoryScorer


class MemoryType(StrEnum):
    """
    Agent Memory 基本分类。
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    REFLECTION = "reflection"


class MemoryManager:
    """
    Agent Memory 生命周期管理器。

    MemoryManager 不直接负责理解自然语言。

    它负责：

        store
        search
        update
        delete

    后续阶段可继续增加：

        admission
        consolidation
        decay
        reflection
        experience learning
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

    # =========================================================
    # Store
    # =========================================================

    def store(
        self,
        content: str,
        *,
        memory_type: MemoryType | str,
        importance: float = 0.5,
    ) -> str:
        """
        保存一条 Memory。

        流程：

            content
               ↓
            validate
               ↓
            embedding
               ↓
            metadata
               ↓
            LanceDB

        Returns
        -------
        memory_id
        """

        content = self._validate_content(
            content
        )

        normalized_type = self._normalize_memory_type(
            memory_type
        )

        importance = self._validate_importance(
            importance
        )

        vector = self.embedder.encode(
            content
        )

        memory_id = str(
            uuid4()
        )

        memory = {
            "id": memory_id,
            "content": content,
            "vector": vector,
            "type": normalized_type,
            "importance": importance,
            "created_at": datetime.now(
                timezone.utc
            ),
        }

        self.table.add(
            [memory]
        )

        return memory_id

    # =========================================================
    # Search
    # =========================================================

    def search(
        self,
        query: str,
        *,
        memory_types: Sequence[MemoryType | str] | None = None,
        min_importance: float | None = None,
        top_k: int = 5,
        candidate_k: int | None = None,
        extra_filter: str | None = None,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """
        搜索 Memory。

        example:

            manager.search(
                "Planner 为什么输出不稳定？",
                memory_types=[
                    MemoryType.REFLECTION
                ],
                min_importance=0.7,
                top_k=5,
            )
        """

        normalized_types: list[str] | None = None

        if memory_types is not None:
            normalized_types = [
                self._normalize_memory_type(
                    memory_type
                )
                for memory_type in memory_types
            ]

        return self.retriever.search(
            query,
            memory_types=normalized_types,
            min_importance=min_importance,
            top_k=top_k,
            candidate_k=candidate_k,
            extra_filter=extra_filter,
            rerank=rerank,
        )

    # =========================================================
    # Get
    # =========================================================

    def get(
        self,
        memory_id: str,
    ) -> dict[str, Any] | None:
        """
        精确获取 Memory。
        """

        return self.retriever.get_by_id(
            memory_id
        )

    # =========================================================
    # Update
    # =========================================================

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        memory_type: MemoryType | str | None = None,
        importance: float | None = None,
    ) -> bool:
        """
        更新 Memory。

        重要规则：

            如果 content 改变：

                content
                   ↓
                embedding

            必须同时重新生成 vector。

        保证：

            vector = Embedding(content)

        始终成立。
        """

        memory_id = self._validate_memory_id(
            memory_id
        )

        values: dict[str, Any] = {}

        # -----------------------------------------
        # Content Update
        # -----------------------------------------

        if content is not None:

            content = self._validate_content(
                content
            )

            values["content"] = content

            # content 改变必须重新生成 vector
            values["vector"] = self.embedder.encode(
                content
            )

        # -----------------------------------------
        # Type Update
        # -----------------------------------------

        if memory_type is not None:
            values["type"] = (
                self._normalize_memory_type(
                    memory_type
                )
            )

        # -----------------------------------------
        # Importance Update
        # -----------------------------------------

        if importance is not None:
            values["importance"] = (
                self._validate_importance(
                    importance
                )
            )

        if not values:
            return False

        where = (
            f"id = {self._sql_string(memory_id)}"
        )

        result = self.table.update(
            where=where,
            values=values,
        )

        rows_updated = getattr(
            result,
            "rows_updated",
            None,
        )

        if rows_updated is None:
            return True

        return rows_updated > 0

    # =========================================================
    # Delete
    # =========================================================

    def delete(
        self,
        memory_id: str,
    ) -> bool:
        """
        删除 Memory。

        当前第五阶段是显式删除。

        后续会扩展成：

            forgetting policy
            memory decay
            superseded memory
            invalid memory
        """

        memory_id = self._validate_memory_id(
            memory_id
        )

        where = (
            f"id = {self._sql_string(memory_id)}"
        )

        result = self.table.delete(
            where
        )

        num_deleted = getattr(
            result,
            "num_deleted_rows",
            None,
        )

        if num_deleted is None:
            return True

        return num_deleted > 0

    # =========================================================
    # Validators
    # =========================================================

    @staticmethod
    def _validate_content(
        content: str,
    ) -> str:

        if not isinstance(
            content,
            str,
        ):
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

        if not isinstance(
            memory_id,
            str,
        ):
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
            return MemoryType(
                value
            ).value

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
