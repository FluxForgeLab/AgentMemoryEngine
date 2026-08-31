# embedding/embedder.py

from __future__ import annotations

from collections.abc import Sequence

from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class TextEmbedder:
    """
    文本 Embedding 服务。

    职责：
        text -> vector

    不负责：
        - Memory 分类
        - LanceDB 存储
        - 检索
        - Memory 评分
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        self._model_name = model_name
        self._normalize_embeddings = normalize_embeddings

        self._model = SentenceTransformer(
            model_name,
            device=device,
        )

        dimension = self._model.get_embedding_dimension()

        if dimension is None:
            raise RuntimeError(
                f"Cannot determine embedding dimension for model: {model_name}"
            )

        self._dimension = int(dimension)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        """
        Embedding 向量维度。

        例如：
            paraphrase-multilingual-MiniLM-L12-v2 -> 384
        """
        return self._dimension

    def encode(self, text: str) -> list[float]:
        """
        将单条文本转换为 Embedding。
        """

        text = self._validate_text(text)

        vector = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self._normalize_embeddings,
            show_progress_bar=False,
        )

        return vector.astype("float32").tolist()

    def encode_many(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 32,
    ) -> list[list[float]]:
        """
        批量生成 Embedding。

        后面导入 Markdown / PDF / Logs 时会使用。
        """

        if not texts:
            return []

        validated_texts = [
            self._validate_text(text)
            for text in texts
        ]

        vectors = self._model.encode(
            validated_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self._normalize_embeddings,
            show_progress_bar=False,
        )

        return [
            vector.astype("float32").tolist()
            for vector in vectors
        ]

    @staticmethod
    def _validate_text(text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        text = text.strip()

        if not text:
            raise ValueError("text cannot be empty")

        return text