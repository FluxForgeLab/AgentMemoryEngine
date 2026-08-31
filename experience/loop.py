from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .model import Experience, ExecutionOutcome, Reflection, RetrievedExperience
from .reflector import Reflector
from .repository import ExperienceRepository


class MemoryPublisher(Protocol):
    """只描述 ExperienceLoop 真正需要的 MemoryManager 能力。"""

    def store(
        self,
        content: str,
        *,
        memory_type: Any,
        importance: float = 0.5,
    ) -> str:
        ...


@dataclass(frozen=True)
class ExperienceContext:
    task: str
    experiences: list[RetrievedExperience]

    def render(self) -> str:
        if not self.experiences:
            return "No relevant past experience was retrieved."

        blocks: list[str] = []
        for index, item in enumerate(self.experiences, start=1):
            exp = item.experience
            blocks.append(
                "\n".join(
                    [
                        f"[Experience {index}]",
                        f"Previous task: {exp.task}",
                        f"Lesson: {exp.lesson}",
                        f"Experience score: {exp.score:.3f}",
                        f"Retrieval score: {item.rank_score:.3f}",
                    ]
                )
            )
        return "\n\n".join(blocks)


@dataclass(frozen=True)
class ExperienceRunResult:
    task: str
    context: ExperienceContext
    outcome: ExecutionOutcome
    reflection: Reflection
    stored_experience: Experience | None


class ExperienceLoop:
    """
    第六阶段的核心闭环。

    before_task:
        Task -> retrieve past experiences

    after_task:
        Task + Action + Result -> Reflection -> Store Experience

    run:
        将两部分组合成一个完整闭环。
    """

    def __init__(
        self,
        repository: ExperienceRepository,
        reflector: Reflector,
        *,
        min_store_score: float = 0.6,
        retrieve_min_score: float = 0.5,
        retrieve_top_k: int = 5,
        memory_publisher: MemoryPublisher | None = None,
        reflection_memory_type: Any = "reflection",
    ) -> None:
        if not 0.0 <= min_store_score <= 1.0:
            raise ValueError("min_store_score must be between 0 and 1")
        if not 0.0 <= retrieve_min_score <= 1.0:
            raise ValueError("retrieve_min_score must be between 0 and 1")
        if retrieve_top_k <= 0:
            raise ValueError("retrieve_top_k must be > 0")

        self.repository = repository
        self.reflector = reflector
        self.min_store_score = min_store_score
        self.retrieve_min_score = retrieve_min_score
        self.retrieve_top_k = retrieve_top_k
        self.memory_publisher = memory_publisher
        self.reflection_memory_type = reflection_memory_type

    def before_task(self, task: str) -> ExperienceContext:
        experiences = self.repository.search(
            task,
            min_score=self.retrieve_min_score,
            top_k=self.retrieve_top_k,
        )
        return ExperienceContext(task=task, experiences=experiences)

    def after_task(
        self,
        *,
        task: str,
        outcome: ExecutionOutcome,
    ) -> tuple[Reflection, Experience | None]:
        reflection = self.reflector.reflect(
            task=task,
            action=outcome.action,
            result=outcome.result,
            success=outcome.success,
        )

        if not reflection.should_store:
            return reflection, None

        if reflection.score < self.min_store_score:
            return reflection, None

        experience = Experience.create(
            task=task,
            action=outcome.action,
            result=outcome.result,
            lesson=reflection.lesson,
            score=reflection.score,
            success=outcome.success,
        )

        self.repository.add(experience)

        # 可选：把“压缩后的 Lesson”同步发布到第五阶段通用 Memory 层。
        if self.memory_publisher is not None:
            self.memory_publisher.store(
                reflection.lesson,
                memory_type=self.reflection_memory_type,
                importance=reflection.score,
            )

        return reflection, experience

    def run(
        self,
        task: str,
        executor: Callable[[str, str], ExecutionOutcome],
    ) -> ExperienceRunResult:
        """
        executor 接收：
            task
            rendered_past_experience_context

        返回：
            ExecutionOutcome(action, result, success)
        """

        context = self.before_task(task)
        outcome = executor(task, context.render())

        if not isinstance(outcome, ExecutionOutcome):
            raise TypeError("executor must return ExecutionOutcome")

        reflection, stored = self.after_task(task=task, outcome=outcome)

        return ExperienceRunResult(
            task=task,
            context=context,
            outcome=outcome,
            reflection=reflection,
            stored_experience=stored,
        )
