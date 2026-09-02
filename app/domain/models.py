from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"
    reflection = "reflection"
    experience = "experience"


class SearchMethod(str, Enum):
    keyword = "keyword"
    vector = "vector"
    hybrid = "hybrid"
    agentic = "agentic"


class GateDecision(str, Enum):
    retrieve = "retrieve"
    skip = "skip"


class Memory(BaseModel):
    id: str
    content: str
    memory_type: MemoryType
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    vector: list[float]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        content: str,
        memory_type: MemoryType,
        importance: float,
        metadata: dict[str, Any],
        vector: list[float],
    ) -> "Memory":
        now = datetime.now(timezone.utc)
        return cls(
            id=f"mem_{uuid4().hex}",
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
            vector=vector,
            created_at=now,
            updated_at=now,
        )


class RetrieveGateResult(BaseModel):
    decision: GateDecision
    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class RetrievalPlan(BaseModel):
    should_retrieve: bool
    method: SearchMethod | None = None
    memory_types: list[MemoryType] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)
    budget_chars: int = 3500
    profile: str = "none"
