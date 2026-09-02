from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lancedb.rerankers import RRFReranker
from lancedb.table import Table

from hybrid.index import ensure_experience_search_text_column
from hybrid.types import SearchMode

from .model import Experience, RetrievedExperience
from app.observability.trace import emit

if TYPE_CHECKING:
    from embedding.embedder import TextEmbedder


def open_experience_table(
    embedder: TextEmbedder,
    *,
    db_path: str | None = None,
    table_name: str | None = None,
    migrate_stage6: bool = True,
) -> Table:
    """
    打开或创建 Experience Table。连库细节交给 storage。

    Stage 7 新增 search_text = Task + Lesson。
    打开 Stage 6 老表时默认回填该列。
    """

    from storage import (
        DEFAULT_DB_PATH,
        EXPERIENCE_TABLE_NAME,
        open_experiences_table,
    )

    table = open_experiences_table(
        dimension=embedder.dimension,
        db_path=db_path or DEFAULT_DB_PATH,
        table_name=table_name or EXPERIENCE_TABLE_NAME,
    )

    if migrate_stage6:
        ensure_experience_search_text_column(table)

    return table


class ExperienceRepository:
    """
    Experience 的持久化与检索层。

    Vector / FTS 都围绕 search_text（Task + Lesson）。
    默认 Hybrid Search；ExperienceLoop 的 search(task, ...) 无需改签名。
    """

    def __init__(
        self,
        table: Table,
        embedder: TextEmbedder,
        *,
        retrieval_weight: float = 0.8,
        experience_weight: float = 0.2,
        semantic_weight: float | None = None,
        rrf_k: int = 60,
    ) -> None:
        if semantic_weight is not None:
            retrieval_weight = semantic_weight

        if retrieval_weight < 0 or experience_weight < 0:
            raise ValueError("weights cannot be negative")
        if retrieval_weight + experience_weight <= 0:
            raise ValueError("weights sum must be > 0")

        total = retrieval_weight + experience_weight
        self.retrieval_weight = retrieval_weight / total
        self.experience_weight = experience_weight / total
        self.table = table
        self.embedder = embedder
        self.rrf_k = rrf_k

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
        mode: SearchMode | str = SearchMode.HYBRID,
        min_score: float = 0.0,
        top_k: int = 5,
        candidate_k: int | None = None,
        success_only: bool = False,
        prefilter: bool = True,
    ) -> list[RetrievedExperience]:
        task = _require_text(task, "task")
        mode = SearchMode(mode)

        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        if top_k <= 0:
            raise ValueError("top_k must be > 0")

        candidate_k = candidate_k or max(top_k * 4, top_k)
        candidate_k = max(candidate_k, top_k)

        count_rows = getattr(self.table, "count_rows", None)
        if callable(count_rows) and count_rows() == 0:
            emit("stage57.search", layer="experience", mode=mode.value, task=task, hits=0, empty=True)
            return []

        filters = [f"score >= {float(min_score)}"]
        if success_only:
            filters.append("success = true")
        where = " AND ".join(filters)

        if mode is SearchMode.VECTOR:
            rows = self._vector_search(
                task=task,
                where=where,
                candidate_k=candidate_k,
                prefilter=prefilter,
            )
        elif mode is SearchMode.KEYWORD:
            rows = self._keyword_search(
                task=task,
                where=where,
                candidate_k=candidate_k,
                prefilter=prefilter,
            )
        else:
            rows = self._hybrid_search(
                task=task,
                where=where,
                candidate_k=candidate_k,
                prefilter=prefilter,
            )

        ranked: list[RetrievedExperience] = []
        for rank, row in enumerate(rows, start=1):
            retrieval_score = 1.0 / float(rank)
            semantic_score = self._semantic_score(row.get("_distance"))
            experience_score = max(
                0.0,
                min(float(row.get("score", 0.0)), 1.0),
            )
            rank_score = (
                retrieval_score * self.retrieval_weight
                + experience_score * self.experience_weight
            )
            ranked.append(
                RetrievedExperience(
                    experience=self._row_to_experience(row),
                    semantic_score=semantic_score,
                    retrieval_score=retrieval_score,
                    rank_score=rank_score,
                    search_mode=mode.value,
                )
            )

        ranked.sort(key=lambda item: item.rank_score, reverse=True)
        trimmed = ranked[:top_k]
        emit(
            "stage57.search",
            layer="experience",
            mode=mode.value,
            task=task,
            hits=len(trimmed),
        )
        return trimmed

    def delete(self, experience_id: str) -> None:
        experience_id = _require_text(experience_id, "experience_id")
        self.table.delete(f"id = {_sql_string(experience_id)}")

    def _vector_search(
        self,
        *,
        task: str,
        where: str,
        candidate_k: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        query_vector = self.embedder.encode(task)
        return (
            self.table.search(
                query_vector,
                vector_column_name="vector",
                query_type="vector",
            )
            .distance_type("cosine")
            .where(where, prefilter=prefilter)
            .select(self._select_columns(include_distance=True))
            .limit(candidate_k)
            .to_list()
        )

    def _keyword_search(
        self,
        *,
        task: str,
        where: str,
        candidate_k: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        return (
            self.table.search(
                task,
                query_type="fts",
                fts_columns="search_text",
            )
            .phrase_query(False)
            .where(where, prefilter=prefilter)
            .select(self._select_columns(include_score=True))
            .limit(candidate_k)
            .to_list()
        )

    def _hybrid_search(
        self,
        *,
        task: str,
        where: str,
        candidate_k: int,
        prefilter: bool,
    ) -> list[dict[str, Any]]:
        query_vector = self.embedder.encode(task)
        reranker = RRFReranker(K=self.rrf_k, return_score="all")
        return (
            self.table.search(
                query_type="hybrid",
                vector_column_name="vector",
                fts_columns="search_text",
            )
            .vector(query_vector)
            .text(task)
            .distance_type("cosine")
            .phrase_query(False)
            .where(where, prefilter=prefilter)
            .rerank(reranker, normalize="rank")
            .select(self._select_columns())
            .limit(candidate_k)
            .to_list()
        )

    @staticmethod
    def _select_columns(
        *,
        include_distance: bool = False,
        include_score: bool = False,
    ) -> list[str]:
        columns = [
            "id",
            "task",
            "action",
            "result",
            "lesson",
            "search_text",
            "score",
            "success",
            "created_at",
        ]
        if include_distance:
            columns.append("_distance")
        if include_score:
            columns.append("_score")
        return columns

    @staticmethod
    def _semantic_score(distance: Any) -> float:
        if distance is None:
            return 0.0
        try:
            # LanceDB cosine distance 约在 [0, 2]
            return max(0.0, min(1.0, 1.0 - float(distance) / 2.0))
        except (TypeError, ValueError):
            return 0.0

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
