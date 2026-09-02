import asyncio
import inspect

from app.adapters.embedding import MockEmbeddingProvider, QwenEmbeddingProvider
from app.adapters.reranker import QwenReranker


def test_embedding_is_deterministic():
    provider = MockEmbeddingProvider(dim=32)

    a = asyncio.run(provider.embed("hello world"))
    b = asyncio.run(provider.embed("hello world"))

    assert a == b
    assert len(a) == 32


def test_mock_embedding_uses_chinese_bigrams():
    provider = MockEmbeddingProvider(dim=32)
    vector = asyncio.run(provider.embed("失败原因"))
    assert any(x != 0.0 for x in vector)


def test_qwen_provider_wraps_vl_adapter():
    assert "BailianQwen3VLEmbeddingAdapter" in inspect.getsource(QwenEmbeddingProvider)
    assert "BailianQwen3VLRerankerAdapter" in inspect.getsource(QwenReranker)
