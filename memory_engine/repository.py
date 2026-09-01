from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from hybrid.index import FTSProfile, create_fts_index
from memory_engine.domain import (
    MemoryRecord,
    MultimodalInput,
    RerankCandidate,
)
from storage import (
    DEFAULT_DB_PATH,
    QWEN_MULTIMODAL_TABLE_NAME,
    open_qwen_multimodal_table as _open_qwen_multimodal_table,
    qwen_multimodal_schema,
)


TABLE_NAME = QWEN_MULTIMODAL_TABLE_NAME


def open_table(
    db: Any | None = None,
    embedder: Any | None = None,
    *,
    dimension: int | None = None,
    table_name: str = TABLE_NAME,
    db_path: str = DEFAULT_DB_PATH,
):
    """
    打开/创建 qwen_multimodal_memories。

    兼容引入源码的 (db, embedder)，
    以及项目既有的 dimension=... 开表方式。
    本地 LanceDB 没有 table_exists，用 table_name in db。
    """

    dim = dimension
    if dim is None and embedder is not None:
        dim = int(embedder.descriptor.dimension)
    if dim is None:
        raise TypeError("embedder or dimension is required")

    if db is not None:
        if table_name in db:
            table = db.open_table(table_name)
        else:
            table = db.create_table(
                table_name,
                schema=qwen_multimodal_schema(dim),
            )
    else:
        table = _open_qwen_multimodal_table(
            dimension=dim,
            db_path=db_path,
            table_name=table_name,
        )

    _ensure_table_compatible(table, embedder, dimension=dim)
    return table


def create_indexes(table: Any, *, replace: bool = False) -> None:
    create_fts_index(
        table,
        "text",
        profile=FTSProfile.MULTILINGUAL_CODE,
        replace=replace,
    )


class MultimodalMemoryRepository:
    def __init__(self, table: Any, embedder: Any) -> None:
        self.table = table
        self.embedder = embedder

    def add(self, memory: MemoryRecord) -> str:
        d = self.embedder.descriptor
        vector = self.embedder.embed(memory.content)
        self.table.add(
            [
                {
                    "id": memory.id,
                    "modality": memory.content.modality(),
                    "text": memory.content.searchable_text() or None,
                    "image": (
                        memory.content.images[0]
                        if memory.content.images
                        else None
                    ),
                    "video": (
                        memory.content.videos[0]
                        if memory.content.videos
                        else None
                    ),
                    "source_uri": memory.source_uri,
                    "importance": memory.importance,
                    "metadata_json": json.dumps(
                        memory.metadata,
                        ensure_ascii=False,
                    ),
                    "created_at": memory.created_at,
                    "embedding_space_id": d.space_id,
                    "embedding_model": d.model,
                    "embedding_dimension": d.dimension,
                    "vector": vector,
                }
            ]
        )
        return memory.id

    def vector_search(
        self,
        query: MultimodalInput,
        *,
        top_k: int = 40,
    ) -> list[RerankCandidate]:
        if _is_empty_table(self.table):
            return []

        d = self.embedder.descriptor
        vector = self.embedder.embed(query)
        rows = (
            self.table.search(
                vector,
                query_type="vector",
                vector_column_name="vector",
            )
            .distance_type("cosine")
            .where(
                "embedding_space_id = " + _sql(d.space_id),
                prefilter=True,
            )
            .limit(top_k)
            .to_list()
        )
        return _to_candidates(rows, "vector")

    def keyword_search(
        self,
        query_text: str,
        *,
        top_k: int = 40,
    ) -> list[RerankCandidate]:
        query_text = query_text.strip()
        if not query_text:
            return []
        if _is_empty_table(self.table):
            return []

        d = self.embedder.descriptor
        rows = (
            self.table.search(
                query_text,
                query_type="fts",
                fts_columns="text",
            )
            .phrase_query(False)
            .where(
                "embedding_space_id = " + _sql(d.space_id),
                prefilter=True,
            )
            .limit(top_k)
            .to_list()
        )
        return _to_candidates(rows, "keyword")


def _ensure_table_compatible(
    table: Any,
    embedder: Any | None,
    *,
    dimension: int,
) -> None:
    names = list(getattr(table.schema, "names", []))
    if "embedding_space_id" not in names:
        raise RuntimeError("old table needs migration")

    if "vector" not in names:
        return

    vector_type = table.schema.field("vector").type
    list_size = getattr(vector_type, "list_size", None)
    expected = (
        int(embedder.descriptor.dimension)
        if embedder is not None
        else int(dimension)
    )
    if list_size is not None and int(list_size) != expected:
        raise RuntimeError(
            f"vector dimension mismatch: table={list_size}, embedder={expected}"
        )


def _is_empty_table(table: Any) -> bool:
    count_rows = getattr(table, "count_rows", None)
    return callable(count_rows) and count_rows() == 0


def _to_candidates(rows: list[dict[str, Any]], source: str) -> list[RerankCandidate]:
    out = []
    for rank, row in enumerate(rows, start=1):
        content = MultimodalInput.mixed(
            texts=[row["text"]] if row.get("text") else [],
            images=[row["image"]] if row.get("image") else [],
            videos=[row["video"]] if row.get("video") else [],
        )
        created = row.get("created_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if isinstance(created, datetime) and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        out.append(
            RerankCandidate(
                id=str(row["id"]),
                content=content,
                retrieval_score=1.0 / rank,
                importance=float(row.get("importance", 0.5)),
                created_at=created,
                source_uri=row.get("source_uri"),
                metadata={"_recall_source": source},
            )
        )
    return out


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
