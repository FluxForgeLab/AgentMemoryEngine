from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import MemoryType, SearchMethod


class MemoryCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    memory_type: MemoryType
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    memory_type: MemoryType | None = None
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] | None = None


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    method: SearchMethod = SearchMethod.hybrid
    memory_types: list[MemoryType] | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, Any] | None = None


class PrepareContextRequest(BaseModel):
    task: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class MemoryResponse(BaseModel):
    id: str
    content: str
    memory_type: MemoryType
    importance: float
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
