from __future__ import annotations

import ast
from pathlib import Path

from multimodal.model import ArtifactChunk
from multimodal.types import Modality


_EXTENSION_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
}


class CodeProcessor:
    """
    Code-aware chunking。

    Python:
        使用 AST，以 Class / Function / AsyncFunction 为边界。

    其他语言:
        当前 Stage 8 使用行窗口 fallback。
        后续可以替换为 tree-sitter Processor，
        而不用改 Repository / Retriever。
    """

    def __init__(
        self,
        *,
        fallback_lines: int = 120,
        fallback_overlap: int = 15,
    ) -> None:
        if fallback_lines <= 0:
            raise ValueError("fallback_lines must be > 0")
        if not 0 <= fallback_overlap < fallback_lines:
            raise ValueError(
                "fallback_overlap must satisfy 0 <= overlap < lines"
            )

        self.fallback_lines = fallback_lines
        self.fallback_overlap = fallback_overlap

    def process(
        self,
        source: str,
    ) -> list[ArtifactChunk]:
        path = Path(source)

        language = _EXTENSION_LANGUAGE.get(
            path.suffix.lower(),
            "unknown",
        )

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if language == "python":
            try:
                return self._python_ast_chunks(
                    text,
                    path=str(path),
                )
            except SyntaxError:
                pass

        return self._fallback_chunks(
            text,
            path=str(path),
            language=language,
        )

    def _python_ast_chunks(
        self,
        text: str,
        *,
        path: str,
    ) -> list[ArtifactChunk]:
        tree = ast.parse(text)
        lines = text.splitlines()

        nodes = [
            node
            for node in tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            )
        ]

        if not nodes:
            return [
                ArtifactChunk.create(
                    modality=Modality.CODE,
                    content=text,
                    source_uri=path,
                    source_type="code",
                    language="python",
                    chunk_index=0,
                )
            ]

        chunks: list[ArtifactChunk] = []

        for index, node in enumerate(nodes):
            end_lineno = getattr(
                node,
                "end_lineno",
                node.lineno,
            )

            content = "\n".join(
                lines[
                    node.lineno - 1:
                    end_lineno
                ]
            ).strip()

            if not content:
                continue

            if isinstance(node, ast.ClassDef):
                symbol_type = "class"
            elif isinstance(
                node,
                ast.AsyncFunctionDef,
            ):
                symbol_type = "async_function"
            else:
                symbol_type = "function"

            chunks.append(
                ArtifactChunk.create(
                    modality=Modality.CODE,
                    content=content,
                    source_uri=path,
                    source_type="code",
                    language="python",
                    symbol=node.name,
                    symbol_type=symbol_type,
                    chunk_index=index,
                    metadata={
                        "line_start": node.lineno,
                        "line_end": end_lineno,
                    },
                )
            )

        return chunks

    def _fallback_chunks(
        self,
        text: str,
        *,
        path: str,
        language: str,
    ) -> list[ArtifactChunk]:
        lines = text.splitlines()

        chunks: list[ArtifactChunk] = []

        step = (
            self.fallback_lines
            - self.fallback_overlap
        )

        for chunk_index, start in enumerate(
            range(
                0,
                len(lines),
                step,
            )
        ):
            end = min(
                start + self.fallback_lines,
                len(lines),
            )

            content = "\n".join(
                lines[start:end]
            ).strip()

            if not content:
                continue

            chunks.append(
                ArtifactChunk.create(
                    modality=Modality.CODE,
                    content=content,
                    source_uri=path,
                    source_type="code",
                    language=language,
                    chunk_index=chunk_index,
                    metadata={
                        "line_start": start + 1,
                        "line_end": end,
                    },
                )
            )

            if end >= len(lines):
                break

        return chunks
