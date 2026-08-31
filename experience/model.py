from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ExecutionOutcome:
    """一次 Agent 执行的最小可观测结果。"""

    action: str
    result: str
    success: bool | None = None


@dataclass(frozen=True)
class Reflection:
    """Reflector 对一次执行提炼出的可复用经验。"""

    lesson: str
    score: float
    should_store: bool = True
    reasoning: str | None = None

    def __post_init__(self) -> None:
        if not self.lesson.strip():
            raise ValueError("lesson cannot be empty")
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be between 0 and 1")


@dataclass(frozen=True)
class Experience:
    """
    Experience Table 对应的数据模型。

    源设计中的核心字段：
        task / action / result / lesson / score

    工程上补充：
        id / success / created_at
    """

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
        task = _require_text(task, "task")
        action = _require_text(action, "action")
        result = _require_text(result, "result")
        lesson = _require_text(lesson, "lesson")
        score = float(score)
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0 and 1")

        return cls(
            id=str(uuid4()),
            task=task,
            action=action,
            result=result,
            lesson=lesson,
            score=score,
            success=success,
            created_at=datetime.now(timezone.utc),
        )

    def embedding_text(self) -> str:
        """用于 Experience 语义检索的文本。"""
        return f"Task:\n{self.task}\n\nLesson:\n{self.lesson}"

    def to_record(self, vector: list[float]) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "action": self.action,
            "result": self.result,
            "lesson": self.lesson,
            "score": self.score,
            "success": self.success,
            "created_at": self.created_at,
            "vector": vector,
        }


@dataclass(frozen=True)
class RetrievedExperience:
    experience: Experience
    semantic_score: float
    rank_score: float


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty")
    return value
