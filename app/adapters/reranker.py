from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings
from app.domain.interfaces import Reranker
from memory_engine.adapters.qwen3_vl_reranker import BailianQwen3VLRerankerAdapter
from memory_engine.domain import MultimodalInput, RerankCandidate
from memory_engine.providers.bailian import (
    BailianClient,
    BailianConfig,
    qwen_rerank_model,
)


class MockReranker(Reranker):
    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        query_tokens = set(query.lower().split())

        def lexical_overlap(item: dict[str, Any]) -> float:
            content_tokens = set(item["content"].lower().split())
            if not query_tokens:
                return 0.0
            return len(query_tokens & content_tokens) / len(query_tokens)

        enriched = []
        for item in candidates:
            row = dict(item)
            base_score = float(row.get("score", 0.0))
            overlap = lexical_overlap(row)
            row["rerank_score"] = 0.7 * base_score + 0.3 * overlap
            enriched.append(row)

        enriched.sort(key=lambda x: x["rerank_score"], reverse=True)
        return enriched[:top_k]


class QwenReranker(Reranker):
    """与 02 相同的 qwen3-vl-rerank，不走 OpenAI 兼容 /rerank。"""

    def __init__(self, settings: Settings | None = None):
        client = BailianClient(BailianConfig.from_env())
        self._adapter = BailianQwen3VLRerankerAdapter(
            client,
            model=qwen_rerank_model(),
        )

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        mapped = [
            RerankCandidate(
                id=str(item["id"]),
                content=MultimodalInput.text(str(item["content"])),
                retrieval_score=float(item.get("score", 0.0)),
            )
            for item in candidates
        ]
        by_id = {str(item["id"]): item for item in candidates}

        results = await asyncio.to_thread(
            self._adapter.rerank,
            MultimodalInput.text(query),
            mapped,
            top_k=top_k,
        )

        output = []
        for item in results:
            row = dict(by_id[item.candidate.id])
            row["rerank_score"] = float(item.rerank_score)
            output.append(row)

        return output[:top_k]


def build_reranker(settings: Settings) -> Reranker:
    provider = settings.reranker_provider.lower()

    if provider == "qwen":
        return QwenReranker(settings)

    if provider == "mock":
        return MockReranker()

    raise ValueError(f"Unsupported reranker provider: {provider}")
