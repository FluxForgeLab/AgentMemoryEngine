# memory/retriever.py

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from lancedb.table import Table

from embedding.embedder import TextEmbedder

from .scorer import MemoryScorer


class MemoryRetriever:
    """
    Memory 检索器。

    职责：

        Query
          ↓
        Embedding
          ↓
        Metadata Filter
          ↓
        Vector Search
          ↓
        Candidate Memories
          ↓
        Score / Rerank
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

    def search(
        self,
        query: str,
        *,
        memory_types: Sequence[str] | None = None,
        min_importance: float | None = None,
        top_k: int = 5,
        candidate_k: int | None = None,
        extra_filter: str | None = None,
        prefilter: bool = True,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """
        搜索 Memory。

        Parameters
        ----------
        query:
            用户查询。

        memory_types:
            限定 Memory 类型。

            例如：
                ["reflection"]
                ["semantic", "procedural"]

        min_importance:
            最低 importance。

        top_k:
            最终返回数量。

        candidate_k:
            Vector Search 初始候选数量。

            rerank=True 时建议 candidate_k > top_k。

        extra_filter:
            额外 LanceDB SQL filter。

        prefilter:
            是否在 Vector Search 前执行 Metadata Filter。

        rerank:
            是否使用 MemoryScorer 二次排序。
        """

        query = query.strip()

        if not query:
            raise ValueError("query cannot be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        if min_importance is not None:
            if not 0 <= min_importance <= 1:
                raise ValueError(
                    "min_importance must be between 0 and 1"
                )

        query_vector = self.embedder.encode(query)

        if candidate_k is None:
            candidate_k = top_k * 4 if rerank else top_k

        candidate_k = max(
            candidate_k,
            top_k,
        )

        search = (
            self.table
            .search(
                query_vector,
                vector_column_name="vector",
            )
            .distance_type("cosine")
            .select(
                [
                    "id",
                    "content",
                    "type",
                    "importance",
                    "created_at",
                    "_distance",
                ]
            )
        )

        where = self._build_filter(
            memory_types=memory_types,
            min_importance=min_importance,
            extra_filter=extra_filter,
        )

        if where:
            search = search.where(
                where,
                prefilter=prefilter,
            )

        candidates = (
            search
            .limit(candidate_k)
            .to_list()
        )

        if not rerank:
            return candidates[:top_k]

        reranked = self.scorer.rerank(
            candidates
        )

        return reranked[:top_k]

    def get_by_id(
        self,
        memory_id: str,
    ) -> dict[str, Any] | None:
        """
        根据 ID 精确获取 Memory。

        这里不进行 Vector Search。
        """

        memory_id = memory_id.strip()

        if not memory_id:
            raise ValueError(
                "memory_id cannot be empty"
            )

        where = (
            f"id = {self._sql_string(memory_id)}"
        )

        rows = (
            self.table
            .search()
            .where(where)
            .limit(1)
            .to_list()
        )

        if not rows:
            return None

        return rows[0]

    def _build_filter(
        self,
        *,
        memory_types: Sequence[str] | None,
        min_importance: float | None,
        extra_filter: str | None,
    ) -> str | None:

        filters: list[str] = []

        if memory_types:

            normalized = {
                memory_type.strip()
                for memory_type in memory_types
                if memory_type.strip()
            }

            if normalized:

                sql_values = ", ".join(
                    self._sql_string(value)
                    for value in sorted(normalized)
                )

                filters.append(
                    f"type IN ({sql_values})"
                )

        if min_importance is not None:
            filters.append(
                f"importance >= {float(min_importance)}"
            )

        if extra_filter:
            extra_filter = extra_filter.strip()

            if extra_filter:
                filters.append(
                    f"({extra_filter})"
                )

        if not filters:
            return None

        return " AND ".join(filters)

    @staticmethod
    def _sql_string(value: str) -> str:
        """
        SQL 字符串 literal。

        ' -> ''
        """

        escaped = value.replace(
            "'",
            "''",
        )

        return f"'{escaped}'"