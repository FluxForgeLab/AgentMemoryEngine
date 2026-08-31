from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lancedb.table import Table

from .model import Experience, RetrievedExperience

if TYPE_CHECKING:
    from embedding.embedder import TextEmbedder


def open_experience_table(
    embedder: TextEmbedder,
    *,
    db_path: str | None = None,
    table_name: str | None = None,
) -> Table:
    """打开或创建 Experience Table。连库细节交给 storage。"""

    from storage import (
        DEFAULT_DB_PATH,
        EXPERIENCE_TABLE_NAME,
        open_experiences_table,
    )

    return open_experiences_table(
        dimension=embedder.dimension,
        db_path=db_path or DEFAULT_DB_PATH,
        table_name=table_name or EXPERIENCE_TABLE_NAME,
    )


class ExperienceRepository:
    """
    Experience 的持久化与检索层。

    Experience 的 vector 使用：
        Task + Lesson

    原因：下一次通常拿“当前 Task”来寻找可复用 Lesson。
    """

    def __init__(
        self,
        table: Table,
        embedder: TextEmbedder,
        *,
        semantic_weight: float = 0.8,
        experience_weight: float = 0.2,
    ) -> None:
        if semantic_weight < 0 or experience_weight < 0:
            raise ValueError("weights cannot be negative")
        if semantic_weight + experience_weight <= 0:
            raise ValueError("weights sum must be > 0")

        total = semantic_weight + experience_weight
        self.semantic_weight = semantic_weight / total
        self.experience_weight = experience_weight / total
        self.table = table
        self.embedder = embedder

    def add(self, experience: Experience) -> str:
        vector = self.embedder.encode(experience.embedding_text())
        self.table.add([experience.to_record(vector)])
        return experience.id

    def get(self, experience_id: str) -> Experience | None:
        experience_id = _require_text(experience_id, "experience_id")
        rows = (
            self.table.search()
            .where(f"id = {_sql_string(experience_id)}")
            .limit(1)
            .to_list()
        )
        if not rows:
            return None
        return self._row_to_experience(rows[0])

    def search(
        self,
        task: str,
        *,
        min_score: float = 0.0,
        top_k: int = 5,
        candidate_k: int | None = None,
        success_only: bool = False,
    ) -> list[RetrievedExperience]:
        task = _require_text(task, "task")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        if top_k <= 0:
            raise ValueError("top_k must be > 0")

        candidate_k = candidate_k or max(top_k * 4, top_k)
        candidate_k = max(candidate_k, top_k)

        count_rows = getattr(self.table, "count_rows", None)
        if callable(count_rows) and count_rows() == 0:
            return []

        query_vector = self.embedder.encode(task)

        query = (
            self.table.search(
                query_vector,
                vector_column_name="vector",
            )
            .distance_type("cosine")
            .select(
                [
                    "id",
                    "task",
                    "action",
                    "result",
                    "lesson",
                    "score",
                    "success",
                    "created_at",
                    "_distance",
                ]
            )
        )

        filters = [f"score >= {float(min_score)}"]
        if success_only:
            filters.append("success = true")

        query = query.where(" AND ".join(filters), prefilter=True)
        rows = query.limit(candidate_k).to_list()

        ranked: list[RetrievedExperience] = []
        for row in rows:
            distance = float(row.get("_distance", 2.0))
            # LanceDB cosine distance 约在 [0, 2]，与 MemoryScorer 同一换算
            semantic_score = max(0.0, min(1.0, 1.0 - distance / 2.0))
            experience_score = max(0.0, min(float(row.get("score", 0.0)), 1.0))
            rank_score = (
                semantic_score * self.semantic_weight
                + experience_score * self.experience_weight
            )
            ranked.append(
                RetrievedExperience(
                    experience=self._row_to_experience(row),
                    semantic_score=semantic_score,
                    rank_score=rank_score,
                )
            )

        ranked.sort(key=lambda item: item.rank_score, reverse=True)
        return ranked[:top_k]

    def delete(self, experience_id: str) -> None:
        experience_id = _require_text(experience_id, "experience_id")
        self.table.delete(f"id = {_sql_string(experience_id)}")

    @staticmethod
    def _row_to_experience(row: dict[str, Any]) -> Experience:
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return Experience(
            id=str(row["id"]),
            task=str(row["task"]),
            action=str(row["action"]),
            result=str(row["result"]),
            lesson=str(row["lesson"]),
            score=float(row["score"]),
            success=row.get("success"),
            created_at=created_at,
        )


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty")
    return value


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
