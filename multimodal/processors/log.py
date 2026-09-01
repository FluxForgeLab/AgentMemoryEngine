from __future__ import annotations

import re
from pathlib import Path

from multimodal.model import ArtifactChunk
from multimodal.types import Modality


_LOG_LEVEL = re.compile(
    r"\b(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b",
    re.IGNORECASE,
)


class LogProcessor:
    """
    Log 仍然是文本，但拥有时间/级别/组件等结构。

    Stage 8 先以 line-window 作为 Episode Window，
    Metadata 中抽取常见 level。
    """

    def __init__(
        self,
        *,
        lines_per_chunk: int = 40,
        overlap_lines: int = 5,
    ) -> None:
        if lines_per_chunk <= 0:
            raise ValueError("lines_per_chunk must be > 0")
        if not 0 <= overlap_lines < lines_per_chunk:
            raise ValueError(
                "overlap_lines must satisfy 0 <= overlap < lines_per_chunk"
            )

        self.lines_per_chunk = lines_per_chunk
        self.overlap_lines = overlap_lines

    def process(
        self,
        source: str,
    ) -> list[ArtifactChunk]:
        path = Path(source)

        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        step = (
            self.lines_per_chunk
            - self.overlap_lines
        )

        chunks: list[ArtifactChunk] = []

        for chunk_index, start in enumerate(
            range(0, len(lines), step)
        ):
            end = min(
                start + self.lines_per_chunk,
                len(lines),
            )

            selected = lines[start:end]
            content = "\n".join(
                selected
            ).strip()

            if not content:
                continue

            levels = sorted(
                {
                    match.group(1).upper()
                    for line in selected
                    for match in _LOG_LEVEL.finditer(
                        line
                    )
                }
            )

            chunks.append(
                ArtifactChunk.create(
                    modality=Modality.LOG,
                    content=content,
                    source_uri=str(path),
                    source_type="log",
                    chunk_index=chunk_index,
                    metadata={
                        "line_start": start + 1,
                        "line_end": end,
                        "levels": levels,
                    },
                )
            )

            if end >= len(lines):
                break

        return chunks
