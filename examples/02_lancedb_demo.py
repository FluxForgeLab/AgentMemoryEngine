from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lancedb

from memory_engine.adapters import (
    BailianQwen3VLEmbeddingAdapter,
    BailianQwen3VLRerankerAdapter,
)
from memory_engine.domain import MemoryRecord, MultimodalInput
from memory_engine.pipeline import RetrievalPipeline, RetrievalPolicy
from memory_engine.providers.bailian import (
    BailianClient,
    BailianConfig,
    qwen_embedding_dimension,
    qwen_embedding_model,
    qwen_rerank_model,
)
from memory_engine.repository import (
    MultimodalMemoryRepository,
    create_indexes,
    open_table,
)
from storage import DEFAULT_DB_PATH


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = BailianClient(BailianConfig.from_env())

    embedder = BailianQwen3VLEmbeddingAdapter(
        client,
        model=qwen_embedding_model(),
        dimension=qwen_embedding_dimension(),
    )
    reranker = BailianQwen3VLRerankerAdapter(
        client,
        model=qwen_rerank_model(),
    )

    db = lancedb.connect(DEFAULT_DB_PATH)
    table = open_table(db, embedder)
    create_indexes(table, replace=False)

    repo = MultimodalMemoryRepository(table, embedder)

    repo.add(
        MemoryRecord.create(
            MultimodalInput.text(
                "复杂 Planner 应先 Research，固定 Evidence Context 后再 Plan。"
            ),
            importance=0.9,
            metadata={"type": "reflection"},
        )
    )

    # 图文融合 Memory 示例：
    # repo.add(
    #     MemoryRecord.create(
    #         MultimodalInput.mixed(
    #             texts=["Planner Research Evidence 架构图"],
    #             images=["./data/architecture.png"],
    #         ),
    #         source_uri="./data/architecture.png",
    #     )
    # )

    pipeline = RetrievalPipeline(repo, reranker)

    results = pipeline.search(
        MultimodalInput.text(
            "Planner 为什么输出不稳定？"
        ),
        policy=RetrievalPolicy(
            candidate_k=30,
            rerank_k=10,
            top_k=5,
        ),
    )

    for item in results:
        c = item.candidate
        print(item.rank, item.rerank_score, c.id)
        print(c.content.searchable_text())


if __name__ == "__main__":
    main()
