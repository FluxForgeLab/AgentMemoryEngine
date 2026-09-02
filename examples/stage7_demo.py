from __future__ import annotations

import sys

from embedding.embedder import TextEmbedder
from experience.model import Experience
from experience.repository import (
    ExperienceRepository,
    open_experience_table,
)
from hybrid.index import (
    FTSProfile,
    setup_stage7_indexes,
)
from hybrid.types import SearchMode
from memory import (
    MemoryManager,
    MemoryType,
)
from storage import open_memories_table


def _seed_demo_data(
    memory: MemoryManager,
    experience: ExperienceRepository,
) -> None:
    memory.store(
        "Planner ResearchStageV2 输出不稳定，是因为跳过 Research 直接进入 Plan。",
        memory_type=MemoryType.REFLECTION,
        importance=0.95,
    )
    memory.store(
        "复杂任务应先 Research，再根据 Evidence 生成 Plan。",
        memory_type=MemoryType.PROCEDURAL,
        importance=0.9,
    )
    experience.add(
        Experience.create(
            task="修复 GH-1842 的跨平台路径回归问题",
            action="统一 path separator，并补 Windows/Linux 回归测试。",
            result="路径解析在各平台一致，GH-1842 关闭。",
            lesson="跨平台路径必须先规范化再拼接；issue id 如 GH-1842 应进入可检索文本。",
            score=0.88,
            success=True,
        )
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from app.observability.setup import setup_logging
    from app.observability.trace import bind_turn
    setup_logging(source="example")
    bind_turn()

    embedder = TextEmbedder()

    memory_table = open_memories_table(dimension=embedder.dimension)
    experience_table = open_experience_table(embedder)

    memory = MemoryManager(
        table=memory_table,
        embedder=embedder,
    )
    experience = ExperienceRepository(
        experience_table,
        embedder,
    )

    _seed_demo_data(memory, experience)

    # 已有同名 FTS 时不会重建。
    setup_stage7_indexes(
        memory_table=memory_table,
        experience_table=experience_table,
        profile=FTSProfile.MULTILINGUAL_CODE,
        replace=False,
    )

    query = "Planner ResearchStageV2 为什么不稳定"

    print("\n=== VECTOR ===")
    for item in memory.search(
        query,
        mode=SearchMode.VECTOR,
        top_k=3,
    ):
        print(item["score"], item["content"])

    print("\n=== KEYWORD ===")
    for item in memory.search(
        query,
        mode=SearchMode.KEYWORD,
        top_k=3,
    ):
        print(item["score"], item["content"])

    print("\n=== HYBRID ===")
    for item in memory.search(
        query,
        mode=SearchMode.HYBRID,
        memory_types=[
            MemoryType.REFLECTION,
            MemoryType.PROCEDURAL,
        ],
        top_k=3,
    ):
        print(item["score"], item["content"])

    print("\n=== EXPERIENCE HYBRID ===")
    results = experience.search(
        "修复 GH-1842 的跨平台路径回归问题",
        mode=SearchMode.HYBRID,
        min_score=0.5,
        top_k=5,
    )
    for item in results:
        print(
            f"rank={item.rank_score:.3f}",
            f"mode={item.search_mode}",
            item.experience.lesson,
        )


if __name__ == "__main__":
    main()
