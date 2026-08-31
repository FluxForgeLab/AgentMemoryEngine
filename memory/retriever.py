from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from lancedb.rerankers import RRFReranker
from lancedb.table import Table

from embedding.embedder import TextEmbedder
from hybrid.types import SearchMode

from .scorer import MemoryScorer


class MemoryRetriever:
    """
    第七阶段 Retriever。

    Stage 5:
        Metadata Filter + Vector Search

    Stage 7:
        Metadata Filter
             ↓
        ┌────┼────┐
        │    │    │
      Vector FTS Hybrid
        │    │    │
        └────┴────┘
             ↓
      Unified Rank Score
             ↓
        MemoryScorer
             ↓
           Top K
    """

    def __init__(
        self,
        table: Table,
        embedder: TextEmbedder,
        *,
        scorer: MemoryScorer | None = None,
        vector_column: str = "vector",
        fts_column: str = "content",
        rrf_k: int = 60,
    ) -> None:
        if rrf_k <= 0:
            raise ValueError(
                "rrf_k must be > 0"
            )

        self.table = table
        self.embedder = embedder
        self.scorer = scorer or MemoryScorer()
        self.vector_column = vector_column
        self.fts_column = fts_column
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        *,
        mode: SearchMode | str = SearchMode.HYBRID,
        memory_types: Sequence[str] | None = None,
        min_importance: float | None = None,
        top_k: int = 5,
        candidate_k: int | None = None,
        extra_filter: str | None = None,
        prefilter: bool = True,
        rerank: bool | None = None,
        rerank_memory: bool = True,
    ) -> list[dict[str, Any]]:
        """
        统一检索入口。

        mode:
            vector
            keyword
            hybrid

        默认进入 Hybrid Search。
        """

        query = self._require_text(
            query,
            "query",
        )

        mode = SearchMode(mode)

        if top_k <= 0:
            raise ValueError(
                "top_k must be > 0"
            )

        if min_importance is not None:
            if not 0.0 <= min_importance <= 1.0:
                raise ValueError(
                    "min_importance must be between 0 and 1"
                )

        candidate_k = (
            candidate_k
            or max(top_k * 4, top_k)
        )
        candidate_k = max(
            candidate_k,
            top_k,
        )

        if rerank is not None:
            rerank_memory = rerank

        count_rows = getattr(self.table, "count_rows", None)
        if callable(count_rows) and count_rows() == 0:
            return []

        where = self._build_filter(
            memory_types=memory_types,
            min_importance=min_importance,
            extra_filter=extra_filter,
        )

        if mode is SearchMode.VECTOR:
            rows = self._vector_search(
                query=query,
                where=where,
                candidate_k=candidate_k,
                prefilter=prefilter,
            )

        elif mode is SearchMode.KEYWORD:
            rows = self._keyword_search(
                query=query,
                where=where,
                candidate_k=candidate_k,
                prefilter=prefilter,
            )

        else:
            rows = self._hybrid_search(
                query=query,
                where=where,
                candidate_k=candidate_k,
                prefilter=prefilter,
            )

        rows = self._attach_rank_relevance(
            rows,
            mode=mode,
        )

        if not rerank_memory:
            return rows[:top_k]

        return self.scorer.rerank(
            rows
        )[:top_k]

    def vector_search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.search(
            query,
            mode=SearchMode.VECTOR,
            **kwargs,
        )

    def keyword_search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.search(
            query,
            mode=SearchMode.KEYWORD,
            **kwargs,
        )

    def hybrid_search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.search(
            query,
            mode=SearchMode.HYBRID,
            **kwargs,
        )

    def get_by_id(
        self,
        memory_id: str,
    ) -> dict[str, Any] | None:
        memory_id = self._require_text(
            memory_id,
            "memory_id",
        )

        rows = (
            self.table.search()
            .where(
                f"id = {self._sql_string(memory_id)}"
            )
            .limit(1)
            .to_list()
        )

        return rows[0] if rows else None

    def _vector_search(
        self,
        *,
        query: str,
        where: str | None,
        candidate_k: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        query_vector = self.embedder.encode(
            query
        )

        builder = (
            self.table.search(
                query_vector,
                vector_column_name=self.vector_column,
                query_type="vector",
            )
            .distance_type("cosine")
            .select(
                self._select_columns(include_distance=True)
            )
        )

        if where:
            builder = builder.where(
                where,
                prefilter=prefilter,
            )

        return (
            builder
            .limit(candidate_k)
            .to_list()
        )

    def _keyword_search(
        self,
        *,
        query: str,
        where: str | None,
        candidate_k: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        builder = (
            self.table.search(
                query,
                query_type="fts",
                fts_columns=self.fts_column,
            )
            # False = terms query，而不是强制 exact phrase。
            .phrase_query(False)
            .select(
                self._select_columns(include_score=True)
            )
        )

        if where:
            builder = builder.where(
                where,
                prefilter=prefilter,
            )

        return (
            builder
            .limit(candidate_k)
            .to_list()
        )

    def _hybrid_search(
        self,
        *,
        query: str,
        where: str | None,
        candidate_k: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        """
        显式提供：
            query vector
            query text

        因为本项目的 Embedding 由 TextEmbedder 独立负责，
        不依赖 LanceDB EmbeddingFunction。
        """

        query_vector = self.embedder.encode(
            query
        )

        reranker = RRFReranker(
            K=self.rrf_k,
            return_score="all",
        )

        builder = (
            self.table.search(
                query_type="hybrid",
                vector_column_name=self.vector_column,
                fts_columns=self.fts_column,
            )
            .vector(query_vector)
            .text(query)
            .distance_type("cosine")
            .phrase_query(False)
            .rerank(
                reranker,
                # 使用 rank 归一化，避免直接混合不同 score space。
                normalize="rank",
            )
            .select(
                self._select_columns()
            )
        )

        if where:
            builder = builder.where(
                where,
                prefilter=prefilter,
            )

        return (
            builder
            .limit(candidate_k)
            .to_list()
        )

    @staticmethod
    def _attach_rank_relevance(
        rows: list[dict[str, Any]],
        *,
        mode: SearchMode,
    ) -> list[dict[str, Any]]:
        """
        将不同 Retriever 的最终“排名”统一成一个 [0,1] relevance。

        为什么不用原始分数？

            Vector: cosine distance
            FTS: BM25 score
            Hybrid: RRF relevance score

        它们不是同一个 score space。

        第七阶段采用非常透明的 Reciprocal Rank：

            relevance = 1 / rank

        这样 MemoryScorer 只需要消费一个统一信号。
        """

        ranked: list[dict[str, Any]] = []

        for rank, row in enumerate(
            rows,
            start=1,
        ):
            item = dict(row)

            item["_search_mode"] = mode.value
            item["_retrieval_rank"] = rank
            item["_retrieval_score"] = (
                1.0 / float(rank)
            )

            ranked.append(item)

        return ranked

    @staticmethod
    def _select_columns(
        *,
        include_distance: bool = False,
        include_score: bool = False,
    ) -> list[str]:
        columns = [
            "id",
            "content",
            "type",
            "importance",
            "created_at",
        ]
        if include_distance:
            columns.append("_distance")
        if include_score:
            columns.append("_score")
        return columns

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
                value.strip()
                for value in memory_types
                if isinstance(value, str) and value.strip()
            }

            if normalized:
                values = ", ".join(
                    self._sql_string(value)
                    for value in sorted(normalized)
                )

                filters.append(
                    f"type IN ({values})"
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
    def _require_text(
        value: str,
        field: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{field} must be a string"
            )

        value = value.strip()

        if not value:
            raise ValueError(
                f"{field} cannot be empty"
            )

        return value

    @staticmethod
    def _sql_string(
        value: str,
    ) -> str:
        escaped = value.replace(
            "'",
            "''",
        )

        return f"'{escaped}'"
