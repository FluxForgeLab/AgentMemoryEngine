from __future__ import annotations

from pathlib import Path
from typing import Any


class OpenClipEmbedder:
    """
    LanceDB OpenCLIP Adapter。

    关键性质：
        text embedding
        image embedding

    位于同一个 CLIP vector space。

    因此 ImageRepository 支持：
        text -> image search
        image -> image search

    这里显式生成 vector，不把模型逻辑耦合到 Table Schema，
    与现有 TextEmbedder 架构保持一致。
    """

    def __init__(
        self,
        *,
        name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        try:
            from lancedb.embeddings import get_registry
        except ImportError as exc:
            raise RuntimeError(
                "OpenClipEmbedder requires lancedb"
            ) from exc

        self._model = (
            get_registry()
            .get("open-clip")
            .create(
                name=name,
                pretrained=pretrained,
                device=device,
                normalize=normalize,
            )
        )

        self.dimension = int(
            self._model.ndims()
        )

    def encode_text(
        self,
        text: str,
    ) -> list[float]:
        text = _require_text(
            text,
            "text",
        )

        value = (
            self._model
            .compute_query_embeddings(text)
        )

        return _first_vector(value)

    def encode_image(
        self,
        image: str | Path | bytes | Any,
    ) -> list[float]:
        value = (
            self._model
            .compute_query_embeddings(image)
        )

        return _first_vector(value)

    def encode_source_image(
        self,
        image: str | Path | bytes | Any,
    ) -> list[float]:
        value = (
            self._model
            .compute_source_embeddings(
                [image]
            )
        )

        return _first_vector(value)


def _first_vector(value: Any) -> list[float]:
    """
    兼容 ndarray / list[np.ndarray] / list[list[float]]。
    """

    if hasattr(value, "tolist"):
        value = value.tolist()

    if not isinstance(value, list):
        value = list(value)

    if not value:
        raise RuntimeError(
            "embedding function returned no vectors"
        )

    if isinstance(
        value[0],
        (list, tuple),
    ):
        vector = value[0]
    else:
        vector = value

    return [
        float(item)
        for item in vector
    ]


def _require_text(
    value: str,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field} must be a string"
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{field} cannot be empty"
        )

    return value
