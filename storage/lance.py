# storage/lance.py

from __future__ import annotations

import lancedb
import pyarrow as pa
from lancedb.table import Table


DEFAULT_DB_PATH = "./database/lance"
DEFAULT_TABLE_NAME = "memories"
EXPERIENCE_TABLE_NAME = "experiences"
ARTIFACT_TABLE_NAME = "artifact_memories"
IMAGE_TABLE_NAME = "image_memories"
QWEN_MULTIMODAL_TABLE_NAME = "qwen_multimodal_memories"


def memories_schema(dimension: int) -> pa.Schema:
    """
    memories 表 schema。

    vector 长度必须与 Embedding 模型维度一致。
    """

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("content", pa.string()),
            pa.field(
                "vector",
                pa.list_(pa.float32(), dimension),
            ),
            pa.field("type", pa.string()),
            pa.field("importance", pa.float64()),
            pa.field(
                "created_at",
                pa.timestamp("us", tz="UTC"),
            ),
        ]
    )


def open_memories_table(
    *,
    dimension: int,
    db_path: str = DEFAULT_DB_PATH,
    table_name: str = DEFAULT_TABLE_NAME,
) -> Table:
    """
    打开已有 memories 表；不存在则按 schema 创建。

    不负责加载 Embedding 模型，只接收 dimension。
    """

    db = lancedb.connect(db_path)

    # 本地连接没有 table_exists；用 __contains__ / list_tables
    if table_name in db:
        return db.open_table(table_name)

    return db.create_table(
        table_name,
        schema=memories_schema(dimension),
    )


def experiences_schema(dimension: int) -> pa.Schema:
    """
    experiences 表 schema。

    设计核心字段：
        task / action / result / lesson / score

    Stage 7 检索列：
        search_text = Task + Lesson

    工程补充：
        id / success / created_at / vector
    """

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("task", pa.string()),
            pa.field("action", pa.string()),
            pa.field("result", pa.string()),
            pa.field("lesson", pa.string()),
            pa.field("search_text", pa.string()),
            pa.field("score", pa.float64()),
            pa.field("success", pa.bool_()),
            pa.field(
                "created_at",
                pa.timestamp("us", tz="UTC"),
            ),
            pa.field(
                "vector",
                pa.list_(pa.float32(), dimension),
            ),
        ]
    )


def open_experiences_table(
    *,
    dimension: int,
    db_path: str = DEFAULT_DB_PATH,
    table_name: str = EXPERIENCE_TABLE_NAME,
) -> Table:
    """
    打开已有 experiences 表；不存在则按 schema 创建。

    不负责加载 Embedding 模型，只接收 dimension。
    """

    db = lancedb.connect(db_path)

    if table_name in db:
        return db.open_table(table_name)

    return db.create_table(
        table_name,
        schema=experiences_schema(dimension),
    )


def artifact_schema(dimension: int) -> pa.Schema:
    """
    artifact_memories：text / code / document / log 共用文本向量空间。
    """

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("modality", pa.string()),
            pa.field("content", pa.string()),
            pa.field("source_uri", pa.string()),
            pa.field("source_type", pa.string()),
            pa.field("language", pa.string()),
            pa.field("symbol", pa.string()),
            pa.field("symbol_type", pa.string()),
            pa.field("page", pa.int32()),
            pa.field("chunk_index", pa.int32()),
            pa.field("metadata_json", pa.string()),
            pa.field(
                "created_at",
                pa.timestamp("us", tz="UTC"),
            ),
            pa.field(
                "vector",
                pa.list_(pa.float32(), dimension),
            ),
        ]
    )


def image_schema(dimension: int) -> pa.Schema:
    """
    image_memories：OpenCLIP 空间，不与文本 embedding 混列。
    """

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("uri", pa.string()),
            pa.field("caption", pa.string()),
            pa.field("width", pa.int32()),
            pa.field("height", pa.int32()),
            pa.field("metadata_json", pa.string()),
            pa.field(
                "created_at",
                pa.timestamp("us", tz="UTC"),
            ),
            pa.field(
                "vector",
                pa.list_(pa.float32(), dimension),
            ),
        ]
    )


def open_artifact_table(
    *,
    dimension: int,
    db_path: str = DEFAULT_DB_PATH,
    table_name: str = ARTIFACT_TABLE_NAME,
) -> Table:
    db = lancedb.connect(db_path)

    if table_name in db:
        return db.open_table(table_name)

    return db.create_table(
        table_name,
        schema=artifact_schema(dimension),
    )


def open_image_table(
    *,
    dimension: int,
    db_path: str = DEFAULT_DB_PATH,
    table_name: str = IMAGE_TABLE_NAME,
) -> Table:
    db = lancedb.connect(db_path)

    if table_name in db:
        return db.open_table(table_name)

    return db.create_table(
        table_name,
        schema=image_schema(dimension),
    )


def qwen_multimodal_schema(dimension: int) -> pa.Schema:
    """
    qwen_multimodal_memories：Qwen3-VL fusion 空间。

    与 memories / experiences / artifact_memories / image_memories
    不混用同一 vector 列。
    """

    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("modality", pa.string()),
            pa.field("text", pa.string()),
            pa.field("image", pa.string()),
            pa.field("video", pa.string()),
            pa.field("source_uri", pa.string()),
            pa.field("importance", pa.float64()),
            pa.field("metadata_json", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
            pa.field("embedding_space_id", pa.string()),
            pa.field("embedding_model", pa.string()),
            pa.field("embedding_dimension", pa.int32()),
            pa.field(
                "vector",
                pa.list_(pa.float32(), dimension),
            ),
        ]
    )


def open_qwen_multimodal_table(
    *,
    dimension: int,
    db_path: str = DEFAULT_DB_PATH,
    table_name: str = QWEN_MULTIMODAL_TABLE_NAME,
) -> Table:
    db = lancedb.connect(db_path)

    if table_name in db:
        return db.open_table(table_name)

    return db.create_table(
        table_name,
        schema=qwen_multimodal_schema(dimension),
    )
