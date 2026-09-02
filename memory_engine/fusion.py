from collections import defaultdict
from dataclasses import replace

from app.observability.trace import emit


def rrf(lists, *, k=60, limit=50):
    scores = defaultdict(float)
    records = {}
    for weight, items in lists:
        for rank, item in enumerate(items, start=1):
            scores[item.id] += float(weight) / (k + rank)
            records[item.id] = item

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    emit(
        "vl.rrf",
        input_sets=len(lists),
        count=len(ordered),
        k=k,
        limit=limit,
    )
    if not ordered:
        return []
    max_score = ordered[0][1] or 1.0

    return [
        replace(
            records[item_id],
            retrieval_score=score / max_score,
        )
        for item_id, score in ordered
    ]
