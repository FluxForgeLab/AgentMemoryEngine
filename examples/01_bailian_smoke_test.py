from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_engine.adapters import (
    BailianQwen3VLEmbeddingAdapter,
    BailianQwen3VLRerankerAdapter,
)
from memory_engine.domain import MultimodalInput, RerankCandidate
from memory_engine.providers.bailian import (
    BailianClient,
    BailianConfig,
    qwen_embedding_dimension,
    qwen_embedding_model,
    qwen_rerank_model,
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from app.observability.setup import setup_logging
    from app.observability.trace import bind_turn
    setup_logging(source="example")
    bind_turn()

    config = BailianConfig.from_env()
    client = BailianClient(config)

    embedder = BailianQwen3VLEmbeddingAdapter(
        client,
        model=qwen_embedding_model(),
        dimension=qwen_embedding_dimension(),
    )

    query = MultimodalInput.text(
        "Planner 为什么应该先执行 Research？"
    )

    vector = embedder.embed(query)
    print("Embedding OK")
    print(embedder.descriptor.space_id)
    print("dimension =", len(vector))
    print("head =", vector[:5])

    reranker = BailianQwen3VLRerankerAdapter(
        client,
        model=qwen_rerank_model(),
    )

    candidates = [
        RerankCandidate(
            id="a",
            content=MultimodalInput.text(
                "复杂规划任务应先收集 Evidence，再进入 Plan。"
            ),
            retrieval_score=0.9,
        ),
        RerankCandidate(
            id="b",
            content=MultimodalInput.text(
                "Docker 镜像由多层文件系统组成。"
            ),
            retrieval_score=0.7,
        ),
    ]

    print("Rerank:")
    for item in reranker.rerank(query, candidates, top_k=2):
        print(item.rank, item.candidate.id, item.rerank_score)


if __name__ == "__main__":
    main()
