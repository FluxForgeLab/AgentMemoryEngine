from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_agent_harness, get_memory_service
from app.api.schemas import (
    MemoryCreateRequest,
    MemoryResponse,
    MemorySearchRequest,
    MemoryUpdateRequest,
    PrepareContextRequest,
)
from app.application.memory_service import MemoryService
from app.harness.runtime import AgentHarness


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
    return {"status": "ok", "stage": 10}


@router.post("/memories", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/memories/search")
async def search_memories(
    request: MemorySearchRequest,
    service: MemoryService = Depends(get_memory_service),
):
    results = await service.search_memory(
        query=request.query,
        method=request.method,
        top_k=request.top_k,
        memory_types=request.memory_types,
        filters=request.filters,
    )
    return {
        "query": request.query,
        "method": request.method,
        "results": results,
    }


@router.post("/agent/prepare-context")
async def prepare_agent_context(
    request: PrepareContextRequest,
    harness: AgentHarness = Depends(get_agent_harness),
):
    return await harness.prepare_context(
        task=request.task,
        context=request.context,
    )


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return to_response(memory)


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
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


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    if not await service.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
