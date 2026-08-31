# memory/scorer.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, log
from typing import Any


_LN2 = log(2.0)


@dataclass(frozen=True)
class ScoreWeights:
    """
    Rerank 权重。

    三项之和不必为 1，会在计分时归一化。
    """

    semantic: float = 0.6
    importance: float = 0.25
    recency: float = 0.15

    def __post_init__(self) -> None:
        total = (
            self.semantic
            + self.importance
            + self.recency
        )

        if total <= 0:
            raise ValueError(
                "score weights must sum to a positive value"
            )


class MemoryScorer:
    """
    Memory 二次排序。

    输入 Vector Search 候选，输出带分数字段的 Memory：

        semantic_score
        importance_score
        recency_score
        score
    """

    def __init__(
        self,
        *,
        weights: ScoreWeights | None = None,
        recency_half_life_days: float = 14.0,
    ) -> None:
        self.weights = weights or ScoreWeights()
        self.recency_half_life_days = recency_half_life_days

    def rerank(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scored = [
            self.score(candidate)
            for candidate in candidates
        ]

        scored.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return scored

    def score(
        self,
        memory: dict[str, Any],
    ) -> dict[str, Any]:
        semantic_score = self._semantic_score(memory)
        importance_score = self._importance_score(memory)
        recency_score = self._recency_score(memory)

        weights = self.weights
        total = (
            weights.semantic
            + weights.importance
            + weights.recency
        )

        final_score = (
            weights.semantic * semantic_score
            + weights.importance * importance_score
            + weights.recency * recency_score
        ) / total

        return {
            **memory,
            "semantic_score": semantic_score,
            "importance_score": importance_score,
            "recency_score": recency_score,
            "score": final_score,
        }

    @staticmethod
    def _semantic_score(
        memory: dict[str, Any],
    ) -> float:
        distance = memory.get("_distance")

        if distance is None:
            return 0.0

        # LanceDB cosine distance 约在 [0, 2]
        return max(
            0.0,
            min(1.0, 1.0 - float(distance) / 2.0),
        )

    @staticmethod
    def _importance_score(
        memory: dict[str, Any],
    ) -> float:
        importance = memory.get("importance", 0.0)

        return max(
            0.0,
            min(1.0, float(importance)),
        )

    def _recency_score(
        self,
        memory: dict[str, Any],
    ) -> float:
        created_at = memory.get("created_at")

        if created_at is None:
            return 0.0

        if not isinstance(created_at, datetime):
            return 0.0

        if created_at.tzinfo is None:
            created_at = created_at.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(timezone.utc)
        age_seconds = (
            now - created_at
        ).total_seconds()
        age_days = max(0.0, age_seconds / 86400.0)

        half_life = self.recency_half_life_days

        if half_life <= 0:
            return 1.0 if age_days == 0 else 0.0

        return exp(-age_days * _LN2 / half_life)
