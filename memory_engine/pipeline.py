from __future__ import annotations

from dataclasses import dataclass

from memory_engine.domain import MultimodalInput, RerankResult
from memory_engine.fusion import rrf
from memory_engine.ports import MemoryRepository, RerankerAdapter
from app.observability.trace import emit, span


@dataclass(frozen=True)
class RetrievalPolicy:
    candidate_k: int = 40
    rerank_k: int = 10
    top_k: int = 5
    vector_weight: float = 1.0
    keyword_weight: float = 1.0
    enable_keyword: bool = True
    enable_rerank: bool = True


class RetrievalPipeline:
    def __init__(
        self,
        repository: MemoryRepository,
        reranker: RerankerAdapter,
    ) -> None:
        self.repository = repository
        self.reranker = reranker

    def search(
        self,
        query: MultimodalInput,
        *,
        policy: RetrievalPolicy | None = None,
    ) -> list[RerankResult]:
        policy = policy or RetrievalPolicy()
        with span("vl.search"):
            vector = self.repository.vector_search(
                query, top_k=policy.candidate_k
            )
            lists = [(policy.vector_weight, vector)]

            if policy.enable_keyword and query.searchable_text():
                keyword = self.repository.keyword_search(
                    query.searchable_text(),
                    top_k=policy.candidate_k,
                )
                lists.append((policy.keyword_weight, keyword))

            fused = rrf(lists, limit=policy.candidate_k)

            if policy.enable_rerank:
                reranked = self.reranker.rerank(
                    query,
                    fused,
                    top_k=min(policy.rerank_k, len(fused)),
                )
            else:
                reranked = [
                    RerankResult(x, x.retrieval_score, i)
                    for i, x in enumerate(
                        fused[:policy.rerank_k], start=1
                    )
                ]

            output = sorted(
                reranked,
                key=lambda x: x.rerank_score,
                reverse=True,
            )[:policy.top_k]
            emit(
                "vl.search",
                vector_hits=len(vector),
                fused=len(fused),
                reranked=len(reranked),
                hits=len(output),
                enable_rerank=policy.enable_rerank,
            )
            return output
