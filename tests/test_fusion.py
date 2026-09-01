from memory_engine.domain import MultimodalInput, RerankCandidate
from memory_engine.fusion import rrf

def c(x):
    return RerankCandidate(
        id=x,
        content=MultimodalInput.text(x),
        retrieval_score=1.0,
    )

def test_rrf():
    result = rrf([
        (1.0, [c("A"), c("B"), c("C")]),
        (1.0, [c("C"), c("A"), c("D")]),
    ])
    assert result[0].id in {"A", "C"}
    assert {x.id for x in result} == {"A", "B", "C", "D"}
