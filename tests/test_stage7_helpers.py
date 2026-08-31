from hybrid.index import (
    build_experience_search_text,
)
from hybrid.types import SearchMode
from memory.retriever import MemoryRetriever


def test_search_text_contains_task_and_lesson():
    text = build_experience_search_text(
        "设计 Planner",
        "先 Research 再 Plan",
    )

    assert "设计 Planner" in text
    assert "先 Research 再 Plan" in text


def test_search_modes():
    assert SearchMode("vector") is SearchMode.VECTOR
    assert SearchMode("keyword") is SearchMode.KEYWORD
    assert SearchMode("hybrid") is SearchMode.HYBRID


def test_reciprocal_rank_relevance():
    rows = [
        {"id": "a"},
        {"id": "b"},
        {"id": "c"},
    ]

    ranked = (
        MemoryRetriever
        ._attach_rank_relevance(
            rows,
            mode=SearchMode.HYBRID,
        )
    )

    assert ranked[0]["_retrieval_score"] == 1.0
    assert ranked[1]["_retrieval_score"] == 0.5
    assert ranked[2]["_retrieval_score"] == 1 / 3
