from __future__ import annotations

from app.domain.models import GateDecision, RetrievalPlan
from app.harness.context_builder import MemoryContextBuilder
from app.harness.memory_client import LocalMemoryClient
from app.harness.retrieve_gate import RetrieveGate
from app.harness.retrieval_planner import RetrievalPlanner
from app.observability.trace import emit, span


class AgentHarness:
    def __init__(
        self,
        *,
        gate: RetrieveGate,
        planner: RetrievalPlanner,
        memory_client: LocalMemoryClient,
        context_builder: MemoryContextBuilder,
    ):
        self.gate = gate
        self.planner = planner
        self.memory_client = memory_client
        self.context_builder = context_builder

    async def prepare_context(self, *, task: str, context: dict | None = None) -> dict:
        with span("harness.prepare"):
            emit("harness.prepare.start", task=task, context_keys=list((context or {}).keys()))
            gate_result = self.gate.decide(task, context)

            if gate_result.decision == GateDecision.skip:
                plan = RetrievalPlan(should_retrieve=False)
                emit(
                    "plan.built",
                    should_retrieve=False,
                    method=None,
                    profile=plan.profile,
                )
                emit("harness.prepare.end", skipped=True)
                return {
                    "gate_decision": gate_result.model_dump(),
                    "retrieval_plan": plan.model_dump(),
                    "memories": [],
                    "memory_context": "",
                }

            plan = self.planner.build(task=task, context=context)
            memories = await self.memory_client.search_plan(plan)
            memory_context = self.context_builder.build(
                memories=memories,
                budget_chars=plan.budget_chars,
            )
            emit(
                "harness.prepare.end",
                skipped=False,
                hits=len(memories),
                context_chars=len(memory_context),
            )
            return {
                "gate_decision": gate_result.model_dump(),
                "retrieval_plan": plan.model_dump(),
                "memories": memories,
                "memory_context": memory_context,
            }
