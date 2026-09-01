from __future__ import annotations

import re
from collections.abc import Sequence

from .model import RetrievalPlan
from .types import Modality


_IDENTIFIER = re.compile(
    r"""
    (
        [A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*
        |
        GH-\d+
        |
        [A-Za-z]+-\d+(?:\.\d+)*
        |
        [A-Za-z_][A-Za-z0-9_]*V\d+
    )
    """,
    re.VERBOSE,
)


class MultimodalRouter:
    """
    Stage 8 的第一版 Router。

    目标不是“用 LLM 猜神秘权重”，
    而是输出稳定、可测试的 Retrieval Plan。

    后续可以替换为：
        classifier
        LLM router
        learned policy
    而不改变 Retriever 接口。
    """

    IMAGE_WORDS = (
        "图片",
        "图像",
        "架构图",
        "截图",
        "照片",
        "image",
        "diagram",
        "screenshot",
        "picture",
    )

    CODE_WORDS = (
        "代码",
        "函数",
        "类",
        "方法",
        "源码",
        "实现",
        "function",
        "class",
        "method",
        "source code",
        "implementation",
    )

    DOCUMENT_WORDS = (
        "文档",
        "markdown",
        "readme",
        "pdf",
        "章节",
        "document",
        "manual",
    )

    LOG_WORDS = (
        "日志",
        "报错",
        "错误码",
        "trace",
        "log",
        "error",
        "exception",
        "stack",
    )

    def route(
        self,
        query: str,
        *,
        modalities: Sequence[Modality | str] | None = None,
    ) -> RetrievalPlan:
        query = query.strip()
        if not query:
            raise ValueError(
                "query cannot be empty"
            )

        if modalities:
            normalized = tuple(
                dict.fromkeys(
                    Modality(value)
                    for value in modalities
                )
            )

            artifact = tuple(
                modality
                for modality in normalized
                if modality is not Modality.IMAGE
            )

            return RetrievalPlan(
                artifact_modalities=artifact,
                search_images=(
                    Modality.IMAGE
                    in normalized
                ),
                search_legacy_memory=(
                    Modality.TEXT
                    in normalized
                ),
                artifact_mode="hybrid",
            )

        lowered = query.lower()

        wants_image = any(
            word in lowered
            for word in self.IMAGE_WORDS
        )

        wants_code = (
            any(
                word in lowered
                for word in self.CODE_WORDS
            )
            or bool(
                _IDENTIFIER.search(query)
            )
        )

        wants_document = any(
            word in lowered
            for word in self.DOCUMENT_WORDS
        )

        wants_log = any(
            word in lowered
            for word in self.LOG_WORDS
        )

        artifact_modalities: list[Modality] = []

        if wants_code:
            artifact_modalities.append(
                Modality.CODE
            )

        if wants_document:
            artifact_modalities.append(
                Modality.DOCUMENT
            )

        if wants_log:
            artifact_modalities.append(
                Modality.LOG
            )

        # 普通概念查询：
        # 搜文本、代码、文档；
        # 默认不搜图片，避免每次 query 都跑 CLIP。
        if not (
            wants_image
            or wants_code
            or wants_document
            or wants_log
        ):
            artifact_modalities.extend(
                [
                    Modality.TEXT,
                    Modality.CODE,
                    Modality.DOCUMENT,
                ]
            )

        # 图片查询通常仍可能需要文本记忆来解释上下文。
        search_legacy = (
            not wants_image
            or len(query) > 8
        )

        # Identifier-heavy query：
        # Artifact 内仍然 Hybrid，
        # FTS 会负责精确 token 召回。
        return RetrievalPlan(
            artifact_modalities=tuple(
                dict.fromkeys(
                    artifact_modalities
                )
            ),
            search_images=wants_image,
            search_legacy_memory=search_legacy,
            artifact_mode="hybrid",
            legacy_weight=1.0,
            artifact_weight=1.1 if wants_code else 1.0,
            image_weight=1.2 if wants_image else 1.0,
            candidate_k=20,
        )
