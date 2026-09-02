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
