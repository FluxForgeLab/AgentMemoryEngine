from __future__ import annotations

import re
from pathlib import Path

from multimodal.model import ArtifactChunk
from multimodal.types import Modality


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class MarkdownProcessor:
    """
    Heading-aware Markdown chunking。

    不按固定 token 粗暴切割，
    优先把：
        heading + section body
    作为语义单元。
    """

    def __init__(
        self,
        *,
        max_chars: int = 3500,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        self.max_chars = max_chars

    def process(self, source: str) -> list[ArtifactChunk]:
        path = Path(source)
        text = path.read_text(encoding="utf-8")

        sections = self.process_text(text)

        chunks: list[ArtifactChunk] = []
        for index, section in enumerate(sections):
            chunks.append(
                ArtifactChunk.create(
                    modality=Modality.DOCUMENT,
                    content=section["content"],
                    source_uri=str(path),
                    source_type="markdown",
                    chunk_index=index,
                    metadata={
                        "heading": section["heading"],
                        "heading_level": section["heading_level"],
                    },
                )
            )

        return chunks

    def process_text(
        self,
        text: str,
    ) -> list[dict[str, object]]:
        lines = text.splitlines()

        sections: list[dict[str, object]] = []
        heading = "(root)"
        heading_level = 0
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer

            content = "\n".join(buffer).strip()
            if not content:
                buffer = []
                return

            for piece in self._split_large_section(
                heading,
                content,
            ):
                sections.append(
                    {
                        "heading": heading,
                        "heading_level": heading_level,
                        "content": piece,
                    }
                )

            buffer = []

        for line in lines:
            match = _HEADING_RE.match(line)
            if match:
                flush()
                heading_level = len(match.group(1))
                heading = match.group(2).strip()
                buffer = [line]
            else:
                buffer.append(line)

        flush()
        return sections

    def _split_large_section(
        self,
        heading: str,
        content: str,
    ) -> list[str]:
        if len(content) <= self.max_chars:
            return [content]

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", content)
            if paragraph.strip()
        ]

        result: list[str] = []
        current = ""

        for paragraph in paragraphs:
            candidate = (
                paragraph
                if not current
                else f"{current}\n\n{paragraph}"
            )

            if (
                len(candidate) <= self.max_chars
                or not current
            ):
                current = candidate
                continue

            result.append(current)
            current = paragraph

        if current:
            result.append(current)

        return result
