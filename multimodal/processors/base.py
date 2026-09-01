from __future__ import annotations

from typing import Protocol

from multimodal.model import ArtifactChunk


class Processor(Protocol):
    def process(self, source: str) -> list[ArtifactChunk]:
        ...
