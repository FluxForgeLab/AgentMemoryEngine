from memory_engine.domain import EmbeddingDescriptor, MultimodalInput
from memory_engine.repository import (
    MultimodalMemoryRepository,
    create_indexes,
    open_table,
)


class _DummyEmbedder:
    def __init__(self, dimension: int = 8) -> None:
        self._descriptor = EmbeddingDescriptor(
            provider="test",
            model="dummy",
            dimension=dimension,
            normalized=True,
            space_id=f"test:dummy:fusion:d{dimension}:v1",
        )

    @property
    def descriptor(self):
        return self._descriptor

    def embed(self, content, *, instruct=None):
        raise AssertionError("empty table must not call embed")


def test_empty_qwen_table_skips_embed(tmp_path):
    import lancedb

    embedder = _DummyEmbedder()
    db = lancedb.connect(str(tmp_path / "lance"))
    table = open_table(db, embedder)
    create_indexes(table, replace=False)

    repo = MultimodalMemoryRepository(table, embedder)
    query = MultimodalInput.text("Planner Research")

    assert repo.vector_search(query, top_k=5) == []
    assert repo.keyword_search("Planner Research", top_k=5) == []
