from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from .adapters import LegacyMemoryAdapter
from .model import UnifiedResult
from .repositories.artifact import ArtifactRepository
from .repositories.image import ImageRepository
from .router import MultimodalRouter
from .types import Modality, SearchMode


class MultimodalRetriever:
    """
    Stage 8 的统一检索层。

    Query
      ↓
    Router
      ↓
    ┌──────────────┬───────────────┬─────────────┐
    Legacy Memory  Artifact        Image
    Hybrid         Hybrid          CLIP/Hybrid
    └──────────────┴───────────────┴─────────────┘
      ↓
    Weighted RRF Fusion
      ↓
    Unified Top K
    """

    def __init__(
        self,
        *,
        artifact_repository: ArtifactRepository,
        image_repository: ImageRepository | None = None,
        legacy_memory: LegacyMemoryAdapter | None = None,
        router: MultimodalRouter | None = None,
        fusion_k: int = 60,
    ) -> None:
        if fusion_k <= 0:
            raise ValueError(
                "fusion_k must be > 0"
            )

        self.artifacts = artifact_repository
        self.images = image_repository
        self.legacy = legacy_memory
        self.router = (
            router
            or MultimodalRouter()
        )
        self.fusion_k = fusion_k

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        modalities: list[Modality | str] | None = None,
    ) -> list[UnifiedResult]:
        plan = self.router.route(
            query,
            modalities=modalities,
        )

        ranked_lists: list[
            tuple[
                float,
                list[UnifiedResult],
            ]
        ] = []

        if (
            plan.search_legacy_memory
            and self.legacy is not None
        ):
            rows = self.legacy.search(
                query,
                top_k=plan.candidate_k,
            )

            ranked_lists.append(
                (
                    plan.legacy_weight,
                    rows,
                )
            )

        if plan.artifact_modalities:
            rows = self.artifacts.search(
                query,
                modalities=(
                    plan.artifact_modalities
                ),
                mode=SearchMode(
                    plan.artifact_mode
                ),
                top_k=plan.candidate_k,
            )

            ranked_lists.append(
                (
                    plan.artifact_weight,
                    [
                        self._artifact_to_result(
                            row
                        )
                        for row in rows
                    ],
                )
            )

        if (
            plan.search_images
            and self.images is not None
        ):
            rows = (
                self.images.search_by_text(
                    query,
                    mode=SearchMode.HYBRID,
                    top_k=plan.candidate_k,
                )
            )

            ranked_lists.append(
                (
                    plan.image_weight,
                    [
                        self._image_to_result(
                            row
                        )
                        for row in rows
                    ],
                )
            )

        return self._weighted_rrf(
            ranked_lists,
            top_k=top_k,
        )

    def search_similar_image(
        self,
        image_path: str,
        *,
        top_k: int = 8,
    ) -> list[UnifiedResult]:
        if self.images is None:
            return []

        rows = self.images.search_by_image(
            image_path,
            top_k=top_k,
        )

        return [
            self._image_to_result(row)
            for row in rows
        ]

    def _weighted_rrf(
        self,
        ranked_lists: list[
            tuple[
                float,
                list[UnifiedResult],
            ]
        ],
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        """
        Cross-retriever Fusion。

        这里不能把：
            BM25
            cosine
            CLIP
            legacy Memory score
        直接相加。

        所以使用 weighted RRF：

            score(d) += weight / (K + rank)
        """

        scores: dict[
            tuple[str, str],
            float,
        ] = defaultdict(float)

        records: dict[
            tuple[str, str],
            UnifiedResult,
        ] = {}

        for weight, results in ranked_lists:
            for rank, result in enumerate(
                results,
                start=1,
            ):
                key = (
                    result.source,
                    result.id,
                )

                scores[key] += (
                    float(weight)
                    / (
                        self.fusion_k
                        + rank
                    )
                )

                records[key] = result

        if not scores:
            return []

        maximum = max(
            scores.values()
        ) or 1.0

        output = []

        for key, raw_score in sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:top_k]:
            row = records[key]

            output.append(
                UnifiedResult(
                    id=row.id,
                    source=row.source,
                    modality=row.modality,
                    content=row.content,
                    uri=row.uri,
                    score=raw_score / maximum,
                    metadata=row.metadata,
                    raw=row.raw,
                )
            )

        return output

    @staticmethod
    def _artifact_to_result(
        row: dict[str, Any],
    ) -> UnifiedResult:
        metadata = _load_json(
            row.get(
                "metadata_json"
            )
        )

        metadata.update(
            {
                "source_type": row.get(
                    "source_type"
                ),
                "language": row.get(
                    "language"
                ),
                "symbol": row.get(
                    "symbol"
                ),
                "symbol_type": row.get(
                    "symbol_type"
                ),
                "page": row.get("page"),
                "chunk_index": row.get(
                    "chunk_index"
                ),
            }
        )

        return UnifiedResult(
            id=str(row["id"]),
            source="artifact",
            modality=Modality(
                row["modality"]
            ),
            content=str(
                row.get(
                    "content",
                    "",
                )
            ),
            uri=row.get(
                "source_uri"
            ),
            score=float(
                row.get(
                    "_retrieval_score",
                    0.0,
                )
            ),
            metadata=metadata,
            raw=dict(row),
        )

    @staticmethod
    def _image_to_result(
        row: dict[str, Any],
    ) -> UnifiedResult:
        return UnifiedResult(
            id=str(row["id"]),
            source="image",
            modality=Modality.IMAGE,
            content=str(
                row.get(
                    "caption",
                    "",
                )
            ),
            uri=row.get("uri"),
            score=float(
                row.get(
                    "_retrieval_score",
                    0.0,
                )
            ),
            metadata={
                **_load_json(
                    row.get(
                        "metadata_json"
                    )
                ),
                "width": row.get(
                    "width"
                ),
                "height": row.get(
                    "height"
                ),
            },
            raw=dict(row),
        )


def _load_json(
    value: Any,
) -> dict[str, Any]:
    if not value:
        return {}

    if isinstance(value, dict):
        return dict(value)

    try:
        parsed = json.loads(
            str(value)
        )
    except Exception:
        return {}

    return (
        parsed
        if isinstance(parsed, dict)
        else {}
    )
