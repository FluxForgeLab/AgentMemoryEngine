from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import MemoryType


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


class SearchOptions(BaseModel):
    vector: bool = True
    keyword: bool = True


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    memory_types: list[MemoryType] | None = None
    filters: dict[str, Any] | None = None
    search: SearchOptions = Field(default_factory=SearchOptions)
    rerank: bool = True


class MemoryResponse(BaseModel):
    id: str
    content: str
    memory_type: MemoryType
    importance: float
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SearchResult(BaseModel):
    id: str
    content: str
    memory_type: str
    importance: float
    metadata: dict[str, Any]
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    rerank_score: float | None = None


class MemorySearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
