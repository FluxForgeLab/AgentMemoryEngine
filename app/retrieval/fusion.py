from __future__ import annotations

from typing import Any

from app.observability.trace import emit


def reciprocal_rank_fusion(
    result_sets: list[list[dict[str, Any]]],
    *,
    k: int = 60,
) -> list[dict[str, Any]]:
    """RRF avoids coupling the caller to raw score scales."""

    merged: dict[str, dict[str, Any]] = {}

    for results in result_sets:
        for rank, item in enumerate(results, start=1):
            memory_id = item["id"]

            if memory_id not in merged:
                merged[memory_id] = dict(item)
                merged[memory_id]["score"] = 0.0

            merged[memory_id]["score"] += 1.0 / (k + rank)

            for key, value in item.items():
                if key not in merged[memory_id]:
                    merged[memory_id][key] = value

    output = list(merged.values())
    output.sort(key=lambda x: x["score"], reverse=True)
    emit(
        "fusion.rrf",
        input_sets=len(result_sets),
        input_sizes=[len(x) for x in result_sets],
        count=len(output),
        k=k,
    )
    return output
