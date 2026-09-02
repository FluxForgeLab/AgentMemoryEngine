from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_memory_service
from app.api.schemas import (
    MemoryCreateRequest,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryUpdateRequest,
    SearchResult,
)
from app.application.memory_service import MemoryService


router = APIRouter(prefix="/v1")


def to_response(memory) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        content=memory.content,
        memory_type=memory.memory_type,
        importance=memory.importance,
        metadata=memory.metadata,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post(
    "/memories",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory(
    request: MemoryCreateRequest,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.store_memory(
        content=request.content,
        memory_type=request.memory_type,
        importance=request.importance,
        metadata=request.metadata,
    )
    return to_response(memory)


@router.post(
    "/memories/search",
    response_model=MemorySearchResponse,
)
async def search_memories(
    request: MemorySearchRequest,
    service: MemoryService = Depends(get_memory_service),
):
    results = await service.search_memory(
        query=request.query,
        top_k=request.top_k,
        memory_types=request.memory_types,
        filters=request.filters,
        use_vector=request.search.vector,
        use_keyword=request.search.keyword,
        rerank=request.rerank,
    )

    normalized = []
    for item in results:
        score = float(item.get("rerank_score", item.get("score", 0.0)))
        normalized.append(
            SearchResult(
                id=item["id"],
                content=item["content"],
                memory_type=item["memory_type"],
                importance=float(item["importance"]),
                metadata=item["metadata"],
                score=score,
                vector_score=item.get("vector_score"),
                keyword_score=item.get("keyword_score"),
                rerank_score=item.get("rerank_score"),
            )
        )

    return MemorySearchResponse(
        query=request.query,
        results=normalized,
    )


@router.get(
    "/memories/{memory_id}",
    response_model=MemoryResponse,
)
async def get_memory(
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.get_memory(memory_id)

    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    return to_response(memory)


@router.patch(
    "/memories/{memory_id}",
    response_model=MemoryResponse,
)
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.update_memory(
        memory_id,
        **request.model_dump(exclude_unset=True),
    )

    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    return to_response(memory)


@router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_memory(
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    deleted = await service.delete_memory(memory_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
