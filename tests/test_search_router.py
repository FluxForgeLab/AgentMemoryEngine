import asyncio

from app.adapters.embedding import MockEmbeddingProvider
from app.domain.models import MemoryType, SearchMethod
from app.memory.search.router import SearchRouter


class FakeRepository:
    async def vector_search(self, vector, *, limit, memory_types=None, filters=None):
        return [{
            "id": "v1", "content": "vector result",
            "memory_type": "reflection", "importance": 0.9,
            "metadata": {}, "vector_score": 0.8,
        }]

    async def keyword_search(self, query, *, limit, memory_types=None, filters=None):
        return [{
            "id": "k1", "content": "keyword result",
            "memory_type": "reflection", "importance": 0.8,
            "metadata": {}, "keyword_score": 0.9,
        }]


def test_keyword_is_single_route():
    router = SearchRouter(FakeRepository(), MockEmbeddingProvider(32))
    results = asyncio.run(router.search(
        query="ERR_1001",
        method=SearchMethod.keyword,
        top_k=5,
        memory_types=[MemoryType.reflection],
        filters=None,
    ))
    assert results[0]["route"] == "keyword"


def test_reflection_hybrid_is_vector_anchored():
    router = SearchRouter(FakeRepository(), MockEmbeddingProvider(32))
    results = asyncio.run(router.search(
        query="planner failure",
        method=SearchMethod.hybrid,
        top_k=5,
        memory_types=[MemoryType.reflection],
        filters=None,
    ))
    assert all(x["route"] == "hybrid:vector_anchored" for x in results)
