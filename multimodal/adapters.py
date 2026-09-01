from __future__ import annotations

from typing import Any

from multimodal.model import UnifiedResult
from multimodal.types import Modality


class LegacyMemoryAdapter:
    """
    把 Stage 5~7 MemoryManager 接到 Stage 8 Fusion 层。

    旧 MemoryManager 无需重写。
    """

    def __init__(
        self,
        manager: Any,
    ) -> None:
        self.manager = manager

    def search(
        self,
        query: str,
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        rows = self.manager.search(
            query,
            mode="hybrid",
            top_k=top_k,
        )

        results: list[UnifiedResult] = []

        for row in rows:
            results.append(
                UnifiedResult(
                    id=str(row["id"]),
                    source="legacy_memory",
                    modality=Modality.TEXT,
                    content=str(
                        row.get(
                            "content",
                            "",
                        )
                    ),
                    score=float(
                        row.get(
                            "_retrieval_score",
                            row.get(
                                "score",
                                0.0,
                            ),
                        )
                    ),
                    metadata={
                        "type": row.get("type"),
                        "importance": row.get(
                            "importance"
                        ),
                    },
                    raw=dict(row),
                )
            )

        return results
