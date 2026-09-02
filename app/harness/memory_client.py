from __future__ import annotations

from app.domain.models import RetrievalPlan
from app.application.memory_service import MemoryService


class LocalMemoryClient:
    """Harness 依赖 Client，不依赖 LanceDB。后续可替换 HTTP/gRPC/MCP。"""

    def __init__(self, service: MemoryService):
        self.service = service

    async def search_plan(self, plan: RetrievalPlan) -> list[dict]:
        if not plan.should_retrieve or not plan.method:
            return []

        merged: dict[str, dict] = {}
        for query in plan.queries:
            results = await self.service.search_memory(
                query=query,
                method=plan.method,
                top_k=plan.top_k,
                memory_types=plan.memory_types,
                filters=plan.filters,
            )
            for item in results:
                previous = merged.get(item["id"])
                if previous is None or float(item.get("score", 0.0)) > float(previous.get("score", 0.0)):
                    merged[item["id"]] = dict(item)

        output = list(merged.values())
        output.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return output[:plan.top_k]
