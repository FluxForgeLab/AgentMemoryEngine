from __future__ import annotations

from app.domain.interfaces import EmbeddingProvider, MemoryRepository
from app.memory.search.fusion import reciprocal_rank_fusion
from app.memory.search.strategies import HybridSearchStrategy
from app.observability.trace import emit


class SufficiencyEvaluator:
    """只回答：当前候选是否已经够用。"""

    def is_sufficient(self, results: list[dict]) -> bool:
        if len(results) < 3:
            return False
        best = max(float(x.get("score", 0.0)) for x in results)
        return best >= 0.015


class MultiQueryGenerator:
    """确定性版本；未来可替换为 LLM QueryGenerator Adapter。"""

    REWRITES = (
        ("为什么", "原因"),
        ("之前", "历史"),
        ("上次", "历史"),
        ("失败", "失败原因"),
        ("经验", "历史经验"),
    )

    def generate(self, query: str) -> list[str]:
        variants = [query.strip()]
        for src, dst in self.REWRITES:
            if src in query:
                variants.append(query.replace(src, dst))
        return list(dict.fromkeys(variants))[:3]


class AgenticSearchStrategy:
    def __init__(self, repository: MemoryRepository, embedder: EmbeddingProvider):
        self.first_pass = HybridSearchStrategy(
            repository,
            embedder,
            variant="vector_anchored",
        )
        self.evaluator = SufficiencyEvaluator()
        self.query_generator = MultiQueryGenerator()

    async def search(self, *, query: str, top_k: int, memory_types, filters):
        candidate_k = max(top_k * 3, 15)
        first = await self.first_pass.search(
            query=query,
            top_k=candidate_k,
            memory_types=memory_types,
            filters=filters,
        )

        sufficient = self.evaluator.is_sufficient(first)
        emit(
            "search.agentic.first",
            query=query,
            hits=len(first),
            sufficient=sufficient,
        )

        if sufficient:
            for item in first[:top_k]:
                item["route"] = "agentic:first_pass_sufficient"
            emit("search.agentic.multi", used=False, hits=top_k)
            return first[:top_k]

        rewrites = self.query_generator.generate(query)[1:]
        emit("search.agentic.rewrite", queries=rewrites)
        result_sets = [first]
        for expanded in rewrites:
            result_sets.append(
                await self.first_pass.search(
                    query=expanded,
                    top_k=candidate_k,
                    memory_types=memory_types,
                    filters=filters,
                )
            )

        fused = reciprocal_rank_fusion(result_sets)
        for item in fused:
            item["route"] = "agentic:multi_query"
        trimmed = fused[:top_k]
        emit(
            "search.agentic.multi",
            used=True,
            rounds=len(result_sets),
            round_sizes=[len(x) for x in result_sets],
            hits=len(trimmed),
        )
        return trimmed
