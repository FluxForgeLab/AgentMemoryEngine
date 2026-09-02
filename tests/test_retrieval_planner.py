from app.domain.models import MemoryType, SearchMethod
from app.harness.retrieval_planner import RetrievalPlanner


def test_failure_history_selects_reflection_experience():
    plan = RetrievalPlanner().build(
        task="之前 Planner 为什么失败？",
        context={"project": "harness"},
    )
    assert MemoryType.reflection in plan.memory_types
    assert MemoryType.experience in plan.memory_types
    assert plan.method == SearchMethod.hybrid


def test_complex_task_upgrades_to_agentic():
    plan = RetrievalPlanner().build(
        task="结合之前失败经验和当前架构重新设计 Planner",
        context={"project": "harness"},
    )
    assert plan.method == SearchMethod.agentic
