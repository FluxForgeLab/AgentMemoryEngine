from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ScoreWeights:
    """
    最终 Memory 排序权重。

    relevance:
        第七阶段统一 Retrieval Relevance。
        它可以来自 Vector / FTS / Hybrid 的排名。

    importance:
        Memory 本身的重要程度。

    recency:
        时间新鲜度。
    """

    relevance: float = 0.70
    importance: float = 0.20
    recency: float = 0.10

    def __post_init__(self) -> None:
        values = (
            self.relevance,
            self.importance,
            self.recency,
        )

        if any(value < 0 for value in values):
            raise ValueError("score weights cannot be negative")

        if sum(values) <= 0:
            raise ValueError("score weights sum must be > 0")


class MemoryScorer:
    """
    第七阶段 Memory Scorer。

    关键变化：

        Stage 5:
            semantic similarity
            + importance
            + recency

        Stage 7:
            retrieval relevance
            + importance
            + recency

    retrieval relevance 可以来自：
        - Vector ranking
        - FTS ranking
        - Hybrid/RRF ranking

    从而避免把 BM25、cosine、RRF 的原始分数直接相加。
    """

    def __init__(
        self,
        *,
        weights: ScoreWeights | None = None,
        recency_half_life_days: float = 30.0,
    ) -> None:
        if recency_half_life_days <= 0:
            raise ValueError(
                "recency_half_life_days must be greater than 0"
            )

        self.weights = weights or ScoreWeights()
        self.recency_half_life_days = recency_half_life_days

    def score(
        self,
        memory: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)

        retrieval_score = self.retrieval_score(memory)

        importance_score = self._clamp(
            float(memory.get("importance", 0.5)),
            0.0,
            1.0,
        )

        recency_score = self.calculate_recency_score(
            memory.get("created_at"),
            now=now,
        )

        semantic_score = self.semantic_score(
            memory.get("_distance")
        )

        weights = self._normalized_weights()

        final_score = (
            retrieval_score * weights.relevance
            + importance_score * weights.importance
            + recency_score * weights.recency
        )

        result = dict(memory)

        result["retrieval_score"] = retrieval_score
        result["semantic_score"] = semantic_score
        result["importance_score"] = importance_score
        result["recency_score"] = recency_score
        result["score"] = final_score

        return result

    def rerank(
        self,
        memories: list[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)

        scored = [
            self.score(memory, now=now)
            for memory in memories
        ]

        return sorted(
            scored,
            key=lambda memory: memory["score"],
            reverse=True,
        )

    @staticmethod
    def retrieval_score(memory: Mapping[str, Any]) -> float:
        """
        Retriever 在执行 Vector / FTS / Hybrid 后，
        会统一注入 _retrieval_score。

        该分数由最终排名归一化而来，
        因此不需要直接比较：
            cosine distance
            BM25 score
            RRF score
        这些不同 score space。
        """

        value = float(
            memory.get("_retrieval_score", 0.0)
        )

        return MemoryScorer._clamp(
            value,
            0.0,
            1.0,
        )

    @staticmethod
    def semantic_score(distance: Any) -> float:
        """
        仅用于观察 Vector signal。

        Keyword Search 可能不存在 _distance，
        此时返回 0。
        """

        if distance is None:
            return 0.0

        try:
            similarity = 1.0 - float(distance) / 2.0
        except (TypeError, ValueError):
            return 0.0

        return MemoryScorer._clamp(
            similarity,
            0.0,
            1.0,
        )

    def calculate_recency_score(
        self,
        created_at: Any,
        *,
        now: datetime,
    ) -> float:
        timestamp = self._parse_datetime(
            created_at
        )

        if timestamp is None:
            return 0.5

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        age = (
            now
            - timestamp.astimezone(timezone.utc)
        )

        age_days = max(
            age.total_seconds() / 86400.0,
            0.0,
        )

        decay = (
            math.log(2)
            / self.recency_half_life_days
        )

        return math.exp(
            -decay * age_days
        )

    def _normalized_weights(
        self,
    ) -> ScoreWeights:
        total = (
            self.weights.relevance
            + self.weights.importance
            + self.weights.recency
        )

        return ScoreWeights(
            relevance=self.weights.relevance / total,
            importance=self.weights.importance / total,
            recency=self.weights.recency / total,
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(
                    value.replace(
                        "Z",
                        "+00:00",
                    )
                )
            except ValueError:
                return None

        return None

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(
            minimum,
            min(value, maximum),
        )
