from __future__ import annotations
from memory_engine.domain import (
    MultimodalInput, RerankCandidate, RerankResult,
)
from memory_engine.providers.bailian import BailianClient, image_ref, video_ref
from app.observability.trace import emit

class BailianQwen3VLRerankerAdapter:
    PATH = "services/rerank/text-rerank/text-rerank"
    DEFAULT_INSTRUCT = (
        "Given a memory retrieval query, rank candidates by how useful "
        "they are for answering or completing the current task."
    )

    def __init__(self, client: BailianClient, *,
                 model="qwen3-vl-rerank"):
        self.client = client
        self.model = model

    def rerank(self, query: MultimodalInput, candidates, *,
               top_k=None, instruct=None):
        if not candidates:
            return []

        documents = [self._doc(c) for c in candidates]
        data = self.client.post(
            self.PATH,
            {
                "model": self.model,
                "input": {
                    "query": self._query(query),
                    "documents": documents,
                },
                "parameters": {
                    "return_documents": False,
                    "top_n": min(top_k or len(candidates), len(candidates)),
                    "instruct": instruct or self.DEFAULT_INSTRUCT,
                },
            },
        )

        rows = data.get("output", {}).get("results", [])
        output = [
            RerankResult(
                candidate=candidates[int(row["index"])],
                rerank_score=float(row["relevance_score"]),
                rank=rank,
            )
            for rank, row in enumerate(rows, start=1)
        ]
        emit("vl.rerank", model=self.model, candidates=len(candidates), hits=len(output))
        return output

    def _query(self, query: MultimodalInput):
        query.validate()
        if query.images:
            return {"image": image_ref(query.images[0])}
        if query.texts:
            return {"text": query.searchable_text()}
        raise ValueError("qwen3-vl-rerank query must be text or image")

    def _doc(self, candidate: RerankCandidate):
        kind, value = candidate.provider_primary_view()
        if kind == "image":
            value = image_ref(value)
        elif kind == "video":
            value = video_ref(value)
        return {kind: value}
