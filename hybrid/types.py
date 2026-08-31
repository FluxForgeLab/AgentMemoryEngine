from __future__ import annotations

from enum import StrEnum


class SearchMode(StrEnum):
    """
    第七阶段支持的三种检索模式。

    VECTOR:
        只使用 Embedding / Vector Search。

    KEYWORD:
        只使用 LanceDB FTS / BM25。

    HYBRID:
        Vector + FTS，并使用 RRF 融合结果。
    """

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
