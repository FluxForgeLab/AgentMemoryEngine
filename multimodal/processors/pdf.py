from __future__ import annotations

from pathlib import Path

from multimodal.model import ArtifactChunk
from multimodal.types import Modality


class PDFProcessor:
    """
    Stage 8 基础 PDF Processor。

    当前实现：
        PDF page -> extracted text -> chunk

    注意：
        这里没有声称 PDF = 纯文本。
        表格、页面图片、复杂布局需要更高级 parser
        （例如 MinerU / Docling / multimodal document model）
        才能无损保留。
    """

    def __init__(
        self,
        *,
        max_chars: int = 3000,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        self.max_chars = max_chars

    def process(
        self,
        source: str,
    ) -> list[ArtifactChunk]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PDFProcessor requires pypdf: pip install pypdf"
            ) from exc

        path = Path(source)
        reader = PdfReader(str(path))

        chunks: list[ArtifactChunk] = []
        chunk_index = 0

        for page_index, page in enumerate(
            reader.pages,
            start=1,
        ):
            text = (page.extract_text() or "").strip()
            if not text:
                continue

            for piece in self._split(text):
                chunks.append(
                    ArtifactChunk.create(
                        modality=Modality.DOCUMENT,
                        content=piece,
                        source_uri=str(path),
                        source_type="pdf",
                        page=page_index,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

        return chunks

    def _split(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]

        pieces = []
        start = 0

        while start < len(text):
            end = min(
                start + self.max_chars,
                len(text),
            )
            piece = text[start:end].strip()
            if piece:
                pieces.append(piece)
            start = end

        return pieces
