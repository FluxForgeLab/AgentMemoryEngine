from app.retrieval.fusion import reciprocal_rank_fusion
from memory_engine.domain import MultimodalInput, RerankCandidate
from memory_engine.fusion import rrf


def test_rrf_merges_same_memory():
    a = [
        {"id": "1", "content": "A"},
        {"id": "2", "content": "B"},
    ]
    b = [
        {"id": "2", "content": "B"},
        {"id": "3", "content": "C"},
    ]

    results = reciprocal_rank_fusion([a, b])

    assert results[0]["id"] == "2"


def c(x):
    return RerankCandidate(
        id=x,
        content=MultimodalInput.text(x),
        retrieval_score=1.0,
    )


def test_memory_engine_rrf():
    result = rrf([
        (1.0, [c("A"), c("B"), c("C")]),
        (1.0, [c("C"), c("A"), c("D")]),
    ])
    assert result[0].id in {"A", "C"}
    assert {x.id for x in result} == {"A", "B", "C", "D"}
