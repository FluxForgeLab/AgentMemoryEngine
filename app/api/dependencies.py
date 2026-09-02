from __future__ import annotations

from functools import lru_cache

from app.adapters.embedding import build_embedding_provider
from app.adapters.reranker import build_reranker
from app.application.memory_manager import MemoryManager
from app.application.memory_service import MemoryService
from app.config import get_settings
from app.infrastructure.lancedb_repository import LanceDBMemoryRepository
from app.retrieval.pipeline import RetrievalPipeline


@lru_cache
def get_memory_service() -> MemoryService:
    settings = get_settings()

    embedder = build_embedding_provider(settings)
    reranker = build_reranker(settings)
    embedding_dim = getattr(embedder, "dim", settings.embedding_dim)

    repository = LanceDBMemoryRepository(
        db_path=settings.memory_db_path,
        table_name=settings.memory_table_name,
        embedding_dim=embedding_dim,
    )

    manager = MemoryManager(
        repository=repository,
        embedder=embedder,
    )

    retriever = RetrievalPipeline(
        repository=repository,
        embedder=embedder,
        reranker=reranker,
    )

    return MemoryService(
        manager=manager,
        retriever=retriever,
    )
