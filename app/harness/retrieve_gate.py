from __future__ import annotations

from typing import Any

from app.domain.models import GateDecision, RetrieveGateResult
from app.observability.trace import emit, span


class RetrieveGate:
    """Harness 层：只判断是否值得进入 Memory Retrieval。"""

    HISTORY_SIGNALS = (
        "之前", "上次", "昨天", "历史", "继续", "还记得",
        "曾经", "过去", "当时", "后来",
    )
    EXPERIENCE_SIGNALS = (
        "失败", "经验", "教训", "踩坑", "复盘", "原因",
        "为什么会", "之前怎么", "类似任务",
    )
    PROJECT_SIGNALS = (
        "我们的", "我的项目", "这个项目", "当前项目",
        "planner", "harness", "memory", "agent",
    )
    STATELESS_SIGNALS = (
        "等于多少", "翻译成", "计算", "定义是什么",
    )

    def decide(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> RetrieveGateResult:
        with span("gate.decide"):
            return self._decide(task, context)

    def _decide(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> RetrieveGateResult:
        text = task.lower()
        context = context or {}
        score = 0.0
        reasons: list[str] = []

        history_hits = [x for x in self.HISTORY_SIGNALS if x in text]
        if history_hits:
            score += min(0.55, 0.25 + 0.1 * len(history_hits))
            reasons.append(f"history dependency: {history_hits[:3]}")

        experience_hits = [x for x in self.EXPERIENCE_SIGNALS if x in text]
        if experience_hits:
            score += min(0.35, 0.15 + 0.08 * len(experience_hits))
            reasons.append(f"experience dependency: {experience_hits[:3]}")

        project_hits = [x for x in self.PROJECT_SIGNALS if x in text]
        if project_hits and context:
            score += 0.2
            reasons.append(f"project dependency: {project_hits[:3]}")

        if context.get("project"):
            score += 0.1
            reasons.append("active project context exists")

        stateless_hits = [x for x in self.STATELESS_SIGNALS if x in text]
        if stateless_hits and not history_hits:
            score -= 0.6
            reasons.append(f"stateless task: {stateless_hits[:3]}")

        score = max(0.0, min(1.0, score))
        decision = (
            GateDecision.retrieve if score >= 0.35 else GateDecision.skip
        )
        result = RetrieveGateResult(
            decision=decision,
            score=score,
            reasons=reasons,
        )
        emit(
            "gate.decided",
            decision=result.decision.value,
            score=result.score,
            reasons=result.reasons,
        )
        return result
