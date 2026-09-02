from __future__ import annotations

from functools import lru_cache

from app.adapters.embedding import build_embedding_provider
from app.application.memory_manager import MemoryManager
from app.application.memory_service import MemoryService
from app.config import get_settings
from app.harness.context_builder import MemoryContextBuilder
from app.harness.memory_client import LocalMemoryClient
from app.harness.retrieve_gate import RetrieveGate
from app.harness.retrieval_planner import RetrievalPlanner
from app.harness.runtime import AgentHarness
from app.infrastructure.lancedb_repository import LanceDBMemoryRepository
from app.memory.search.router import SearchRouter


@lru_cache
def get_memory_service() -> MemoryService:
    settings = get_settings()
    embedder = build_embedding_provider(settings)
    embedding_dim = getattr(embedder, "dim", settings.embedding_dim)

    repository = LanceDBMemoryRepository(
        db_path=settings.memory_db_path,
        table_name=settings.memory_table_name,
        embedding_dim=embedding_dim,
    )

    manager = MemoryManager(repository=repository, embedder=embedder)
    search_router = SearchRouter(repository=repository, embedder=embedder)

    return MemoryService(
        manager=manager,
        search_router=search_router,
    )


@lru_cache
def get_agent_harness() -> AgentHarness:
    return AgentHarness(
        gate=RetrieveGate(),
        planner=RetrievalPlanner(),
        memory_client=LocalMemoryClient(get_memory_service()),
        context_builder=MemoryContextBuilder(),
    )
