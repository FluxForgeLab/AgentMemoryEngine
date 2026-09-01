from __future__ import annotations

from typing import Any

from hybrid.index import FTSProfile, create_fts_index
from storage import (
    ARTIFACT_TABLE_NAME,
    DEFAULT_DB_PATH,
    IMAGE_TABLE_NAME,
    artifact_schema,
    image_schema,
    open_artifact_table as _open_artifact_table,
    open_image_table as _open_image_table,
)


ARTIFACT_TABLE = ARTIFACT_TABLE_NAME
IMAGE_TABLE = IMAGE_TABLE_NAME


def open_artifact_table(
    db: Any | None = None,
    *,
    text_vector_dim: int | None = None,
    dimension: int | None = None,
    table_name: str = ARTIFACT_TABLE,
    db_path: str = DEFAULT_DB_PATH,
):
    """
    打开/创建 artifact_memories。

    兼容 Stage 8 源码的 (db, text_vector_dim=...)，
    以及项目既有的 dimension=... 开表方式。
    """

    dim = text_vector_dim if text_vector_dim is not None else dimension
    if dim is None:
        raise TypeError("text_vector_dim or dimension is required")

    if db is not None:
        if table_name in db:
            return db.open_table(table_name)
        return db.create_table(
            table_name,
            schema=artifact_schema(dim),
        )

    return _open_artifact_table(
        dimension=dim,
        db_path=db_path,
        table_name=table_name,
    )


def open_image_table(
    db: Any | None = None,
    *,
    image_vector_dim: int | None = None,
    dimension: int | None = None,
    table_name: str = IMAGE_TABLE,
    db_path: str = DEFAULT_DB_PATH,
):
    dim = image_vector_dim if image_vector_dim is not None else dimension
    if dim is None:
        raise TypeError("image_vector_dim or dimension is required")

    if db is not None:
        if table_name in db:
            return db.open_table(table_name)
        return db.create_table(
            table_name,
            schema=image_schema(dim),
        )

    return _open_image_table(
        dimension=dim,
        db_path=db_path,
        table_name=table_name,
    )


def create_stage8_indexes(
    *,
    artifact_table: Any,
    image_table: Any | None = None,
    replace: bool = False,
) -> None:
    """
    artifact.content / image.caption 使用与 Stage 7 相同的 ngram FTS。
    """

    create_fts_index(
        artifact_table,
        "content",
        profile=FTSProfile.MULTILINGUAL_CODE,
        replace=replace,
    )

    for column in ("modality", "source_type", "language"):
        try:
            artifact_table.create_scalar_index(
                column,
                index_type="BITMAP",
                replace=replace,
            )
        except Exception:
            pass

    if image_table is None:
        return

    create_fts_index(
        image_table,
        "caption",
        profile=FTSProfile.MULTILINGUAL_CODE,
        replace=replace,
    )
