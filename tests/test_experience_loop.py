from __future__ import annotations

from experience.loop import ExperienceLoop
from experience.model import ExecutionOutcome, Reflection, RetrievedExperience
from experience.reflector import CallableReflector


class FakeRepository:
    def __init__(self):
        self.items = []

    def search(self, task, *, min_score, top_k):
        return []

    def add(self, experience):
        self.items.append(experience)
        return experience.id


def test_after_task_stores_high_score_reflection():
    repo = FakeRepository()
    reflector = CallableReflector(
        lambda **_: Reflection(
            lesson="复杂规划任务应先 Research 再 Plan。",
            score=0.9,
            should_store=True,
        )
    )

    loop = ExperienceLoop(repo, reflector, min_store_score=0.6)

    reflection, experience = loop.after_task(
        task="设计 Planner",
        outcome=ExecutionOutcome(
            action="直接 Plan",
            result="输出不稳定",
            success=False,
        ),
    )

    assert reflection.score == 0.9
    assert experience is not None
    assert len(repo.items) == 1
    assert repo.items[0].lesson == "复杂规划任务应先 Research 再 Plan。"


def test_after_task_rejects_low_score_reflection():
    repo = FakeRepository()
    reflector = CallableReflector(
        lambda **_: Reflection(
            lesson="证据不足。",
            score=0.2,
            should_store=True,
        )
    )

    loop = ExperienceLoop(repo, reflector, min_store_score=0.6)

    _, experience = loop.after_task(
        task="设计 Planner",
        outcome=ExecutionOutcome(
            action="直接 Plan",
            result="结果未知",
            success=None,
        ),
    )

    assert experience is None
    assert repo.items == []


def test_after_task_publishes_lesson_to_memory():
    repo = FakeRepository()
    published: list[dict] = []

    class FakeMemory:
        def store(self, content, *, memory_type, importance=0.5):
            published.append(
                {
                    "content": content,
                    "memory_type": memory_type,
                    "importance": importance,
                }
            )
            return "mem-1"

    reflector = CallableReflector(
        lambda **_: Reflection(
            lesson="复杂规划任务应先 Research 再 Plan。",
            score=0.9,
            should_store=True,
        )
    )

    loop = ExperienceLoop(
        repo,
        reflector,
        min_store_score=0.6,
        memory_publisher=FakeMemory(),
        reflection_memory_type="reflection",
    )

    loop.after_task(
        task="设计 Planner",
        outcome=ExecutionOutcome(
            action="直接 Plan",
            result="输出不稳定",
            success=False,
        ),
    )

    assert published == [
        {
            "content": "复杂规划任务应先 Research 再 Plan。",
            "memory_type": "reflection",
            "importance": 0.9,
        }
    ]
