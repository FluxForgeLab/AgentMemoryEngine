from __future__ import annotations

import sys
from pathlib import Path

from embedding.embedder import TextEmbedder
from hybrid.index import FTSProfile, setup_stage7_indexes
from memory import MemoryManager, MemoryType
from multimodal.adapters import LegacyMemoryAdapter
from multimodal.embedders import OpenClipEmbedder
from multimodal.repositories import ArtifactRepository, ImageRepository
from multimodal.retriever import MultimodalRetriever
from multimodal.service import MultimodalMemoryService
from multimodal.storage import create_stage8_indexes, open_artifact_table, open_image_table
from storage import open_memories_table


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from app.observability.setup import setup_logging
    from app.observability.trace import bind_turn
    setup_logging(source="example")
    bind_turn()

    text_embedder = TextEmbedder()

    memories_table = open_memories_table(dimension=text_embedder.dimension)
    artifact_table = open_artifact_table(dimension=text_embedder.dimension)

    clip_embedder = None
    image_table = None
    image_repo = None

    try:
        clip_embedder = OpenClipEmbedder(device="cpu")
        image_table = open_image_table(dimension=clip_embedder.dimension)
        image_repo = ImageRepository(image_table, clip_embedder)
    except Exception as exc:
        print(f"OpenCLIP unavailable, image retrieval disabled: {exc}")

    setup_stage7_indexes(
        memory_table=memories_table,
        profile=FTSProfile.MULTILINGUAL_CODE,
        replace=False,
    )
    create_stage8_indexes(
        artifact_table=artifact_table,
        image_table=image_table,
        replace=False,
    )

    memory = MemoryManager(
        table=memories_table,
        embedder=text_embedder,
    )
    artifact_repo = ArtifactRepository(artifact_table, text_embedder)
    service = MultimodalMemoryService(
        artifact_repository=artifact_repo,
        image_repository=image_repo,
    )

    memory.store(
        "Planner Research 阶段负责在规划前收集任务相关证据。",
        memory_type=MemoryType.SEMANTIC,
        importance=0.8,
    )

    service.ingest_text(
        """
        Agent Planner 在复杂任务中应先执行 Research，
        固定 Evidence Context 后再进入 Plan。
        """,
        source_uri="demo://planner-note",
    )
    service.ingest_file(str(ROOT / "memory" / "retriever.py"))
    service.ingest_file(str(ROOT / "README.md"))

    retriever = MultimodalRetriever(
        artifact_repository=artifact_repo,
        image_repository=image_repo,
        legacy_memory=LegacyMemoryAdapter(memory),
    )

    results = retriever.search(
        "Planner Research 的实现和架构图",
        top_k=8,
    )

    for item in results:
        print(
            f"[{item.modality}] "
            f"score={item.score:.3f} "
            f"source={item.source}"
        )
        print(item.content[:200])
        if item.uri:
            print("uri:", item.uri)
        print()


if __name__ == "__main__":
    main()
