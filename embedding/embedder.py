# embedding/embedder.py

from __future__ import annotations

from collections.abc import Sequence


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class TextEmbedder:
    """
    文本 Embedding 服务。Stage 2~8 共用。

    职责：
        text -> vector

    不负责：
        - Memory 生命周期
        - Chunking
        - LanceDB
        - Routing
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        from sentence_transformers import SentenceTransformer

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
        return self._dimension

    @property
    def normalize_embeddings(self) -> bool:
        return self._normalize_embeddings

    def encode(self, text: str) -> list[float]:
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
