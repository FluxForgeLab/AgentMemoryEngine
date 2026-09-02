import asyncio

from app.adapters.embedding import MockEmbeddingProvider


def test_embedding_is_deterministic():
    provider = MockEmbeddingProvider(dim=32)

    a = asyncio.run(provider.embed("hello world"))
    b = asyncio.run(provider.embed("hello world"))

    assert a == b
    assert len(a) == 32


def test_qwen_provider_wraps_vl_adapter():
    import inspect

    from app.adapters.embedding import QwenEmbeddingProvider
    from app.adapters.reranker import QwenReranker

    assert "BailianQwen3VLEmbeddingAdapter" in inspect.getsource(QwenEmbeddingProvider)
    assert "BailianQwen3VLRerankerAdapter" in inspect.getsource(QwenReranker)
