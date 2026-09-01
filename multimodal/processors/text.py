from __future__ import annotations

from multimodal.model import ArtifactChunk
from multimodal.types import Modality


class TextProcessor:
    def __init__(
        self,
        *,
        max_chars: int = 1800,
        overlap_chars: int = 200,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        if not 0 <= overlap_chars < max_chars:
            raise ValueError(
                "overlap_chars must satisfy 0 <= overlap < max_chars"
            )

        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def process_text(
        self,
        text: str,
        *,
        source_uri: str | None = None,
        source_type: str = "text",
        metadata: dict | None = None,
    ) -> list[ArtifactChunk]:
        text = text.strip()
        if not text:
            return []

        pieces = self._chunk(text)

        return [
            ArtifactChunk.create(
                modality=Modality.TEXT,
                content=piece,
                source_uri=source_uri,
                source_type=source_type,
                chunk_index=index,
                metadata=metadata,
            )
            for index, piece in enumerate(pieces)
        ]

    def process(self, source: str) -> list[ArtifactChunk]:
        with open(source, "r", encoding="utf-8") as f:
            text = f.read()

        return self.process_text(
            text,
            source_uri=source,
            source_type="text_file",
        )

    def _chunk(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]

        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = min(
                start + self.max_chars,
                len(text),
            )

            # 尽量在段落/换行处结束，避免硬切句子。
            if end < len(text):
                window = text[start:end]
                split_at = max(
                    window.rfind("\n\n"),
                    window.rfind("\n"),
                    window.rfind("。"),
                    window.rfind(". "),
                )

                if split_at > self.max_chars // 2:
                    end = start + split_at + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            start = max(
                end - self.overlap_chars,
                start + 1,
            )

        return chunks
