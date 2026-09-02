from __future__ import annotations

from typing import Any

from app.domain.models import MemoryType, RetrievalPlan, SearchMethod


class RetrievalPlanner:
    """Gate 已通过后，构建稳定 RetrievalPlan。"""

    def build(
        self,
        *,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> RetrievalPlan:
        text = task.lower()
        context = context or {}
        memory_types: list[MemoryType] = []

        if any(x in text for x in ("上次", "昨天", "之前做", "发生", "当时")):
            memory_types.append(MemoryType.episodic)

        if any(x in text for x in ("失败", "原因", "复盘", "教训", "为什么")):
            memory_types.extend([MemoryType.reflection, MemoryType.experience])

        if any(x in text for x in ("怎么做", "流程", "步骤", "部署", "实现方法")):
            memory_types.append(MemoryType.procedural)

        if any(x in text for x in ("架构", "设计", "知识", "是什么", "原理")):
            memory_types.append(MemoryType.semantic)

        if not memory_types:
            memory_types = [MemoryType.semantic, MemoryType.experience]

        memory_types = list(dict.fromkeys(memory_types))
        method = self._choose_method(text, memory_types)
        queries = self._build_queries(task, memory_types)

        filters = {
            key: context[key]
            for key in ("project", "agent", "owner")
            if context.get(key)
        }

        profile = {
            SearchMethod.keyword: "exact",
            SearchMethod.vector: "semantic",
            SearchMethod.hybrid: "balanced",
            SearchMethod.agentic: "complex",
        }[method]

        return RetrievalPlan(
            should_retrieve=True,
            method=method,
            memory_types=memory_types,
            queries=queries,
            top_k=8 if method == SearchMethod.agentic else 5,
            filters=filters,
            budget_chars=5000 if method == SearchMethod.agentic else 3500,
            profile=profile,
        )

    def _choose_method(
        self,
        text: str,
        memory_types: list[MemoryType],
    ) -> SearchMethod:
        exact = ("错误码", "error code", "id=", "函数名", "类名", "文件名", "接口名", "精确")
        complex_ = ("结合", "综合", "多个", "跨", "完整分析", "失败经验和", "历史经验和", "重新设计")
        semantic = ("类似", "相关", "为什么", "原因", "经验")

        if any(x in text for x in exact):
            return SearchMethod.keyword
        if any(x in text for x in complex_):
            return SearchMethod.agentic
        if any(x in text for x in semantic):
            return SearchMethod.hybrid
        if memory_types == [MemoryType.semantic]:
            return SearchMethod.vector
        return SearchMethod.hybrid

    def _build_queries(
        self,
        task: str,
        memory_types: list[MemoryType],
    ) -> list[str]:
        queries = [task.strip()]
        if MemoryType.reflection in memory_types:
            queries.append(f"{task.strip()} 失败原因 反思 教训")
        if MemoryType.experience in memory_types:
            queries.append(f"{task.strip()} 历史经验 类似任务")
        if MemoryType.procedural in memory_types:
            queries.append(f"{task.strip()} 步骤 流程 方法")
        return list(dict.fromkeys(queries))[:3]
