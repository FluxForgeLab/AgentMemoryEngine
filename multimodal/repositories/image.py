from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lancedb.rerankers import RRFReranker

from multimodal.embedders import OpenClipEmbedder
from multimodal.model import ImageMemory
from multimodal.types import SearchMode


class ImageRepository:
    """
    Image Memory Repository。

    image vector 使用 OpenCLIP shared space：
        text query -> image
        image query -> image

    caption 另外建立 FTS，
    所以 text query 还能执行：
        CLIP vector + caption FTS -> Hybrid
    """

    def __init__(
        self,
        table: Any,
        embedder: OpenClipEmbedder,
        *,
        rrf_k: int = 60,
    ) -> None:
        self.table = table
        self.embedder = embedder
        self.rrf_k = rrf_k

    def add(
        self,
        image: ImageMemory,
    ) -> str:
        path = image.uri

        width = image.width
        height = image.height

        if (
            width is None
            or height is None
        ):
            try:
                from PIL import Image

                with Image.open(path) as img:
                    width, height = img.size
            except Exception:
                pass

        vector = (
            self.embedder
            .encode_source_image(path)
        )

        self.table.add(
            [
                {
                    "id": image.id,
                    "uri": image.uri,
                    "caption": image.caption,
                    "width": width,
                    "height": height,
                    "metadata_json": json.dumps(
                        image.metadata,
                        ensure_ascii=False,
                    ),
                    "created_at": image.created_at,
                    "vector": vector,
                }
            ]
        )

        return image.id

    def search_by_text(
        self,
        query: str,
        *,
        mode: SearchMode | str = SearchMode.HYBRID,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise ValueError(
                "query cannot be empty"
            )

        mode = SearchMode(mode)

        count_rows = getattr(self.table, "count_rows", None)
        if callable(count_rows) and count_rows() == 0:
            return []

        if mode is SearchMode.KEYWORD:
            rows = (
                self.table.search(
                    query,
                    query_type="fts",
                    fts_columns="caption",
                )
                .phrase_query(False)
                .limit(top_k)
                .to_list()
            )

            return _attach_rank_score(
                rows
            )

        vector = (
            self.embedder
            .encode_text(query)
        )

        if mode is SearchMode.VECTOR:
            rows = (
                self.table.search(
                    vector,
                    query_type="vector",
                    vector_column_name="vector",
                )
                .distance_type("cosine")
                .limit(top_k)
                .to_list()
            )

            return _attach_rank_score(
                rows
            )

        # Hybrid:
        # CLIP text->image vector relevance
        # +
        # caption FTS relevance
        rows = (
            self.table.search(
                query_type="hybrid",
                vector_column_name="vector",
                fts_columns="caption",
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
            .limit(top_k)
            .to_list()
        )

        return _attach_rank_score(
            rows
        )

    def search_by_image(
        self,
        image: str | Path,
        *,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        count_rows = getattr(self.table, "count_rows", None)
        if callable(count_rows) and count_rows() == 0:
            return []

        vector = (
            self.embedder
            .encode_image(image)
        )

        rows = (
            self.table.search(
                vector,
                query_type="vector",
                vector_column_name="vector",
            )
            .distance_type("cosine")
            .limit(top_k)
            .to_list()
        )

        return _attach_rank_score(
            rows
        )


def _attach_rank_score(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []

    for rank, row in enumerate(
        rows,
        start=1,
    ):
        item = dict(row)
        item["_retrieval_rank"] = rank
        item["_retrieval_score"] = (
            1.0 / float(rank)
        )
        output.append(item)

    return output
