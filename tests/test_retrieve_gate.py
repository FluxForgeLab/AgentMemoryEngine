from app.domain.models import GateDecision
from app.harness.retrieve_gate import RetrieveGate


def test_history_task_should_retrieve():
    result = RetrieveGate().decide(
        "继续我们上次 Planner 随机性问题的设计",
        {"project": "harness"},
    )
    assert result.decision == GateDecision.retrieve


def test_simple_stateless_task_should_skip():
    result = RetrieveGate().decide("1 + 1 等于多少")
    assert result.decision == GateDecision.skip
