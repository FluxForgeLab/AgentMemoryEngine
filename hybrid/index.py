from __future__ import annotations

from enum import StrEnum
from typing import Any

import pyarrow as pa


class FTSProfile(StrEnum):
    """
    FTS tokenizer 预设。

    SIMPLE:
        适合主要由英文自然语言组成的数据。

    MULTILINGUAL_CODE:
        使用 ngram，不依赖外部分词模型。
        对中文、代码符号、错误码、版本号、路径等混合文本更稳健。

    CHINESE_JIEBA:
        使用 LanceDB 的 jieba/default tokenizer。
        需要 Lance 的语言模型文件已经安装/可访问。
    """

    SIMPLE = "simple"
    MULTILINGUAL_CODE = "multilingual_code"
    CHINESE_JIEBA = "chinese_jieba"


def create_fts_index(
    table: Any,
    column: str,
    *,
    profile: FTSProfile | str = FTSProfile.MULTILINGUAL_CODE,
    replace: bool = False,
) -> None:
    """
    为指定文本列创建 LanceDB Native FTS Index。

    第七阶段默认 MULTILINGUAL_CODE：
        - ngram tokenizer
        - 2~4 gram
        - 不做 stemming
        - 不移除 stop words

    这样可以避免中文没有空格时 simple tokenizer 无法很好切词，
    同时对 GH-1842、ResearchStageV2、MemoryManager.update 等标识符有效。
    """

    profile = FTSProfile(profile)

    if not replace and _column_has_fts_index(table, column):
        return

    try:
        _create_fts_index(table, column, profile=profile, replace=replace)
    except Exception as exc:
        if replace or not _looks_like_index_exists(exc):
            raise


def _create_fts_index(
    table: Any,
    column: str,
    *,
    profile: FTSProfile,
    replace: bool,
) -> None:
    if profile is FTSProfile.SIMPLE:
        table.create_fts_index(
            column,
            replace=replace,
            base_tokenizer="simple",
            lower_case=True,
            stem=True,
            remove_stop_words=True,
        )
        return

    if profile is FTSProfile.CHINESE_JIEBA:
        table.create_fts_index(
            column,
            replace=replace,
            base_tokenizer="jieba/default",
            lower_case=True,
            stem=False,
            remove_stop_words=False,
            ascii_folding=False,
        )
        return

    table.create_fts_index(
        column,
        replace=replace,
        base_tokenizer="ngram",
        ngram_min_length=2,
        ngram_max_length=4,
        prefix_only=False,
        lower_case=True,
        stem=False,
        remove_stop_words=False,
        ascii_folding=False,
        max_token_length=80,
    )


def ensure_experience_search_text_column(table: Any) -> None:
    """
    将第六阶段 Experience Table 升级为第七阶段结构。

    Stage 6:
        task
        action
        result
        lesson
        score
        ...

    Stage 7 新增:
        search_text = Task + Lesson

    原因：
        Hybrid Search 的 FTS 侧需要一个明确的文本列。
        search_text 保证 Vector 和 FTS 都围绕同一份可复用经验语义进行检索。

    这是一次性迁移函数。
    """

    if "search_text" in table.schema.names:
        return

    table.add_columns(
        [pa.field("search_text", pa.string())]
    )

    row_count = table.count_rows()
    if row_count == 0:
        return

    rows = (
        table.search()
        .select(["id", "task", "lesson"])
        .limit(row_count)
        .to_list()
    )

    for row in rows:
        experience_id = str(row["id"])
        task = str(row.get("task", ""))
        lesson = str(row.get("lesson", ""))

        table.update(
            where=f"id = {_sql_string(experience_id)}",
            values={
                "search_text": build_experience_search_text(
                    task,
                    lesson,
                )
            },
        )


def setup_stage7_indexes(
    *,
    memory_table: Any,
    experience_table: Any | None = None,
    profile: FTSProfile | str = FTSProfile.MULTILINGUAL_CODE,
    replace: bool = False,
) -> None:
    """
    第七阶段统一索引初始化。

    Memory:
        content -> FTS Index

    Experience:
        search_text -> FTS Index
    """

    create_fts_index(
        memory_table,
        "content",
        profile=profile,
        replace=replace,
    )

    if experience_table is not None:
        ensure_experience_search_text_column(
            experience_table
        )

        create_fts_index(
            experience_table,
            "search_text",
            profile=profile,
            replace=replace,
        )


def _column_has_fts_index(table: Any, column: str) -> bool:
    try:
        indexes = table.list_indices()
    except Exception:
        return False

    for index in indexes:
        columns = list(getattr(index, "columns", None) or [])
        index_type = str(getattr(index, "index_type", "")).upper()
        name = str(getattr(index, "name", "")).upper()
        if column not in columns and column.upper() not in name:
            continue
        if "FTS" in index_type or "INVERTED" in index_type or "FTS" in name:
            return True

    return False


def _looks_like_index_exists(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "already exists" in text or "already exist" in text


def build_experience_search_text(
    task: str,
    lesson: str,
) -> str:
    return (
        f"Task:\n{task.strip()}\n\n"
        f"Lesson:\n{lesson.strip()}"
    )


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
