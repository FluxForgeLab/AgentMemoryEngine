from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from hybrid.index import (
    build_experience_search_text,
)


@dataclass(frozen=True)
class ExecutionOutcome:
    action: str
    result: str
    success: bool | None = None


@dataclass(frozen=True)
class Reflection:
    lesson: str
    score: float
    should_store: bool = True
    reasoning: str | None = None

    def __post_init__(self) -> None:
        if not self.lesson.strip():
            raise ValueError(
                "lesson cannot be empty"
            )

        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError(
                "score must be between 0 and 1"
            )


@dataclass(frozen=True)
class Experience:
    id: str
    task: str
    action: str
    result: str
    lesson: str
    score: float
    success: bool | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        task: str,
        action: str,
        result: str,
        lesson: str,
        score: float,
        success: bool | None = None,
    ) -> "Experience":
        task = _require_text(
            task,
            "task",
        )
        action = _require_text(
            action,
            "action",
        )
        result = _require_text(
            result,
            "result",
        )
        lesson = _require_text(
            lesson,
            "lesson",
        )

        score = float(score)

        if not 0.0 <= score <= 1.0:
            raise ValueError(
                "score must be between 0 and 1"
            )

        return cls(
            id=str(uuid4()),
            task=task,
            action=action,
            result=result,
            lesson=lesson,
            score=score,
            success=success,
            created_at=datetime.now(
                timezone.utc
            ),
        )

    def search_text(self) -> str:
        """
        Stage 7 的统一检索文本。

        Vector 和 FTS 都围绕：
            Task + Lesson
        """
        return build_experience_search_text(
            self.task,
            self.lesson,
        )

    def embedding_text(self) -> str:
        """
        保持 Stage 6 API 兼容。
        """
        return self.search_text()

    def to_record(
        self,
        vector: list[float],
    ) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "action": self.action,
            "result": self.result,
            "lesson": self.lesson,
            "search_text": self.search_text(),
            "score": self.score,
            "success": self.success,
            "created_at": self.created_at,
            "vector": vector,
        }


@dataclass(frozen=True)
class RetrievedExperience:
    """
    保留 Stage 6 的：
        semantic_score
        rank_score

    Stage 7 新增：
        retrieval_score
        search_mode
    """

    experience: Experience
    semantic_score: float
    rank_score: float
    retrieval_score: float = 0.0
    search_mode: str = "vector"


def _require_text(
    value: str,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field} must be a string"
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{field} cannot be empty"
        )

    return value
