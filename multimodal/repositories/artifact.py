from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from lancedb.rerankers import RRFReranker

from embedding.embedder import TextEmbedder
from multimodal.model import ArtifactChunk
from multimodal.types import Modality, SearchMode


class ArtifactRepository:
    """
    Text / Code / Document / Log Repository。

    所有这些类型都使用同一个 Text Embedding Space，
    但通过 modality metadata 保持逻辑边界。
    """

    def __init__(
        self,
        table: Any,
        embedder: TextEmbedder,
        *,
        rrf_k: int = 60,
    ) -> None:
        self.table = table
        self.embedder = embedder
        self.rrf_k = rrf_k

    def add_many(
        self,
        chunks: Sequence[ArtifactChunk],
    ) -> list[str]:
        if not chunks:
            return []

        vectors = self.embedder.encode_many(
            [chunk.content for chunk in chunks]
        )

        rows = []

        for chunk, vector in zip(
            chunks,
            vectors,
            strict=True,
        ):
            rows.append(
                {
                    "id": chunk.id,
                    "modality": chunk.modality.value,
                    "content": chunk.content,
                    "source_uri": chunk.source_uri,
                    "source_type": chunk.source_type,
                    "language": chunk.language,
                    "symbol": chunk.symbol,
                    "symbol_type": chunk.symbol_type,
                    "page": chunk.page,
                    "chunk_index": chunk.chunk_index,
                    "metadata_json": json.dumps(
                        chunk.metadata,
                        ensure_ascii=False,
                    ),
                    "created_at": chunk.created_at,
                    "vector": vector,
                }
            )

        self.table.add(rows)

        return [
            chunk.id
            for chunk in chunks
        ]

    def search(
        self,
        query: str,
        *,
        modalities: Sequence[Modality | str] | None = None,
        mode: SearchMode | str = SearchMode.HYBRID,
        top_k: int = 10,
        candidate_k: int | None = None,
        language: str | None = None,
        source_type: str | None = None,
        prefilter: bool = True,
    ) -> list[dict[str, Any]]:
        query = _require_text(
            query,
            "query",
        )
        mode = SearchMode(mode)

        candidate_k = (
            candidate_k
            or max(top_k * 3, top_k)
        )

        count_rows = getattr(self.table, "count_rows", None)
        if callable(count_rows) and count_rows() == 0:
            return []

        where = self._build_filter(
            modalities=modalities,
            language=language,
            source_type=source_type,
        )

        if mode is SearchMode.VECTOR:
            rows = self._vector(
                query,
                where=where,
                limit=candidate_k,
                prefilter=prefilter,
            )

        elif mode is SearchMode.KEYWORD:
            rows = self._fts(
                query,
                where=where,
                limit=candidate_k,
                prefilter=prefilter,
            )

        else:
            rows = self._hybrid(
                query,
                where=where,
                limit=candidate_k,
                prefilter=prefilter,
            )

        return _attach_rank_score(
            rows
        )[:top_k]

    def _vector(
        self,
        query: str,
        *,
        where: str | None,
        limit: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        vector = self.embedder.encode(
            query
        )

        builder = (
            self.table.search(
                vector,
                query_type="vector",
                vector_column_name="vector",
            )
            .distance_type("cosine")
        )

        if where:
            builder = builder.where(
                where,
                prefilter=prefilter,
            )

        return (
            builder
            .limit(limit)
            .to_list()
        )

    def _fts(
        self,
        query: str,
        *,
        where: str | None,
        limit: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        builder = (
            self.table.search(
                query,
                query_type="fts",
                fts_columns="content",
            )
            .phrase_query(False)
        )

        if where:
            builder = builder.where(
                where,
                prefilter=prefilter,
            )

        return (
            builder
            .limit(limit)
            .to_list()
        )

    def _hybrid(
        self,
        query: str,
        *,
        where: str | None,
        limit: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        vector = self.embedder.encode(
            query
        )

        builder = (
            self.table.search(
                query_type="hybrid",
                vector_column_name="vector",
                fts_columns="content",
            )
            .vector(vector)
            .text(query)
            .distance_type("cosine")
            .phrase_query(False)
            .rerank(
                RRFReranker(
                    K=self.rrf_k,
                    return_score="all",
                ),
                normalize="rank",
            )
        )

        if where:
            builder = builder.where(
                where,
                prefilter=prefilter,
            )

        return (
            builder
            .limit(limit)
            .to_list()
        )

    @staticmethod
    def _build_filter(
        *,
        modalities: Sequence[Modality | str] | None,
        language: str | None,
        source_type: str | None,
    ) -> str | None:
        parts: list[str] = []

        if modalities:
            values = sorted(
                {
                    Modality(value).value
                    for value in modalities
                }
            )

            literal = ", ".join(
                _sql_string(value)
                for value in values
            )

            parts.append(
                f"modality IN ({literal})"
            )

        if language:
            parts.append(
                f"language = {_sql_string(language)}"
            )

        if source_type:
            parts.append(
                f"source_type = {_sql_string(source_type)}"
            )

        return (
            " AND ".join(parts)
            if parts
            else None
        )


def _attach_rank_score(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []

    for rank, row in enumerate(
        rows,
        start=1,
    ):
        item = dict(row)
        item["_retrieval_rank"] = rank
        item["_retrieval_score"] = (
            1.0 / float(rank)
        )
        result.append(item)

    return result


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


def _sql_string(
    value: str,
) -> str:
    return "'" + value.replace("'", "''") + "'"
