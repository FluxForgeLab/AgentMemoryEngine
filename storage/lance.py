# storage/lance.py

from __future__ import annotations

import lancedb
import pyarrow as pa
from lancedb.table import Table


DEFAULT_DB_PATH = "./database/lance"
DEFAULT_TABLE_NAME = "memories"
EXPERIENCE_TABLE_NAME = "experiences"


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
