from __future__ import annotations

from enum import StrEnum

from hybrid.types import SearchMode

__all__ = [
    "Modality",
    "SearchMode",
]


class Modality(StrEnum):
    TEXT = "text"
    CODE = "code"
    DOCUMENT = "document"
    LOG = "log"
    IMAGE = "image"
