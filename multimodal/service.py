from __future__ import annotations

from pathlib import Path
from typing import Any

from .model import ImageMemory
from .processors import (
    CodeProcessor,
    LogProcessor,
    MarkdownProcessor,
    PDFProcessor,
    TextProcessor,
)
from .repositories import (
    ArtifactRepository,
    ImageRepository,
)


class MultimodalMemoryService:
    """
    Stage 8 Ingestion Facade。

    重点：
        Processor 负责理解输入格式
        Repository 负责 Embedding + Persist

    因此 MemoryManager 不需要膨胀成 parse_pdf/parse_code God Class。
    """

    def __init__(
        self,
        *,
        artifact_repository: ArtifactRepository,
        image_repository: ImageRepository | None = None,
    ) -> None:
        self.artifacts = artifact_repository
        self.images = image_repository

        self.text_processor = TextProcessor()
        self.markdown_processor = MarkdownProcessor()
        self.pdf_processor = PDFProcessor()
        self.code_processor = CodeProcessor()
        self.log_processor = LogProcessor()

    def ingest_text(
        self,
        text: str,
        *,
        source_uri: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        chunks = (
            self.text_processor
            .process_text(
                text,
                source_uri=source_uri,
                metadata=metadata,
            )
        )

        return self.artifacts.add_many(
            chunks
        )

    def ingest_file(
        self,
        path: str,
    ) -> list[str]:
        suffix = (
            Path(path)
            .suffix
            .lower()
        )

        if suffix in {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".java",
            ".rs",
            ".cpp",
            ".cc",
            ".c",
            ".h",
            ".hpp",
            ".go",
        }:
            chunks = (
                self.code_processor
                .process(path)
            )

        elif suffix in {
            ".md",
            ".markdown",
        }:
            chunks = (
                self.markdown_processor
                .process(path)
            )

        elif suffix == ".pdf":
            chunks = (
                self.pdf_processor
                .process(path)
            )

        elif suffix in {
            ".log",
            ".out",
        }:
            chunks = (
                self.log_processor
                .process(path)
            )

        else:
            chunks = (
                self.text_processor
                .process(path)
            )

        return self.artifacts.add_many(
            chunks
        )

    def ingest_image(
        self,
        path: str,
        *,
        caption: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if self.images is None:
            raise RuntimeError("image repository is not configured")

        image = ImageMemory.create(
            uri=path,
            caption=caption,
            metadata=metadata,
        )

        return self.images.add(
            image
        )
