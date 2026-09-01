from memory_engine.domain import RerankResult

class NoopReranker:
    def rerank(self, query, candidates, *, top_k=None, instruct=None):
        ordered = sorted(
            candidates,
            key=lambda x: x.retrieval_score,
            reverse=True,
        )
        ordered = ordered[:top_k] if top_k else ordered
        return [
            RerankResult(x, x.retrieval_score, i)
            for i, x in enumerate(ordered, start=1)
        ]
