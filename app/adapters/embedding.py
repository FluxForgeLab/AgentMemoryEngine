from __future__ import annotations

import asyncio
import hashlib
import math

from app.config import Settings
from app.domain.interfaces import EmbeddingProvider
from memory_engine.adapters.qwen3_vl_embedding import BailianQwen3VLEmbeddingAdapter
from memory_engine.domain import MultimodalInput
from memory_engine.providers.bailian import (
    BailianClient,
    BailianConfig,
    qwen_embedding_dimension,
    qwen_embedding_model,
)


class MockEmbeddingProvider(EmbeddingProvider):
    """可离线运行的稳定 embedding；支持中文字符 2-gram。"""

    def __init__(self, dim: int = 1024):
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        normalized = "".join(text.lower().split())
        tokens = set(text.lower().split())
        tokens.update(
            normalized[i : i + 2]
            for i in range(max(0, len(normalized) - 1))
        )

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]


class QwenEmbeddingProvider(EmbeddingProvider):
    """Stage 9/10 HTTP 使用与 02 相同的 qwen3-vl-embedding。"""

    def __init__(self, settings: Settings | None = None):
        client = BailianClient(BailianConfig.from_env())
        dimension = qwen_embedding_dimension()
        self._adapter = BailianQwen3VLEmbeddingAdapter(
            client,
            model=qwen_embedding_model(),
            dimension=dimension,
        )
        self.dim = self._adapter.dimension

    async def embed(self, text: str) -> list[float]:
        return await asyncio.to_thread(
            self._adapter.embed,
            MultimodalInput.text(text),
        )


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()

    if provider == "qwen":
        return QwenEmbeddingProvider(settings)

    if provider == "mock":
        return MockEmbeddingProvider(settings.embedding_dim)

    raise ValueError(f"Unsupported embedding provider: {provider}")
