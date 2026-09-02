from __future__ import annotations

import sys

from embedding.embedder import TextEmbedder
from experience import (
    CallableReflector,
    ExperienceLoop,
    ExperienceRepository,
    ExecutionOutcome,
    Reflection,
    open_experience_table,
)
from hybrid.index import (
    FTSProfile,
    setup_stage7_indexes,
)
from memory import MemoryManager, MemoryType
from storage import open_memories_table


def demo_reflection(**kwargs) -> Reflection:
    """
    为了让 Demo 完全离线可运行，这里用确定性函数模拟 Reflection。
    真正接入 Agent 时，把它替换为 LLMReflector 即可。
    """
    result = kwargs["result"]

    if "上下文不足" in result or "不稳定" in result:
        return Reflection(
            lesson="复杂规划任务在生成 Plan 前应先执行 Research，形成稳定的 Evidence Context。",
            score=0.92,
            should_store=True,
            reasoning="失败结果明确指向规划前上下文不足。",
        )

    return Reflection(
        lesson="当前执行记录不足以形成可靠、可泛化的经验。",
        score=0.2,
        should_store=False,
        reasoning="缺少明确的因果证据。",
    )


def first_executor(task: str, past_experience: str) -> ExecutionOutcome:
    print("=== First Run Retrieved Context ===")
    print(past_experience)

    return ExecutionOutcome(
        action="收到任务后直接生成 Plan，没有执行 Research。",
        result="Planner 输出不稳定，主要表现为上下文不足和隐含假设漂移。",
        success=False,
    )


def second_executor(task: str, past_experience: str) -> ExecutionOutcome:
    print("\n=== Second Run Retrieved Context ===")
    print(past_experience)

    return ExecutionOutcome(
        action="先执行 Research 并固定 Evidence Context，再生成 Plan。",
        result="Planner 输出稳定，计划覆盖关键依赖并通过验证。",
        success=True,
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from app.observability.setup import setup_logging
    from app.observability.trace import bind_turn
    setup_logging(source="example")
    bind_turn()

    embedder = TextEmbedder()

    memories_table = open_memories_table(dimension=embedder.dimension)
    experiences_table = open_experience_table(embedder)

    setup_stage7_indexes(
        memory_table=memories_table,
        experience_table=experiences_table,
        profile=FTSProfile.MULTILINGUAL_CODE,
        replace=False,
    )

    memory_manager = MemoryManager(
        table=memories_table,
        embedder=embedder,
    )
    repository = ExperienceRepository(experiences_table, embedder)
    reflector = CallableReflector(demo_reflection)

    loop = ExperienceLoop(
        repository,
        reflector,
        min_store_score=0.6,
        retrieve_min_score=0.5,
        retrieve_top_k=5,
        memory_publisher=memory_manager,
        reflection_memory_type=MemoryType.REFLECTION,
    )

    task = "设计一个稳定的 Agent Planner"

    first = loop.run(task, first_executor)
    print("\nStored first experience:", first.stored_experience is not None)
    if first.stored_experience is not None:
        print("Lesson:", first.stored_experience.lesson)

    second = loop.run(task, second_executor)
    print("\nStored second experience:", second.stored_experience is not None)

    reflections = memory_manager.search(
        task,
        memory_types=[MemoryType.REFLECTION],
        top_k=3,
    )
    print("\n=== Synced Reflection Memories ===")
    if not reflections:
        print("No reflection memories found.")
    for item in reflections:
        print(item["content"])
        print("importance:", item["importance"])
        print()


if __name__ == "__main__":
    main()
