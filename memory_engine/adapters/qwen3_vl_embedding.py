from __future__ import annotations
from memory_engine.domain import EmbeddingDescriptor, MultimodalInput
from memory_engine.providers.bailian import BailianClient, image_ref, video_ref
from app.observability.trace import emit

class BailianQwen3VLEmbeddingAdapter:
    PATH = "services/embeddings/multimodal-embedding/multimodal-embedding"

    def __init__(self, client: BailianClient, *,
                 model="qwen3-vl-embedding", dimension=1024):
        allowed = {2560, 2048, 1536, 1024, 768, 512, 256}
        if dimension not in allowed:
            raise ValueError(f"unsupported dimension: {dimension}")
        self.client = client
        self.model = model
        self.dimension = dimension
        self._descriptor = EmbeddingDescriptor(
            provider="aliyun-bailian",
            model=model,
            dimension=dimension,
            normalized=True,
            space_id=f"aliyun-bailian:{model}:fusion:d{dimension}:v1",
        )

    @property
    def descriptor(self):
        return self._descriptor

    def embed(self, content: MultimodalInput, *, instruct=None):
        content.validate()
        contents = []
        contents += [{"text": x} for x in content.texts]
        contents += [{"image": image_ref(x)} for x in content.images]
        contents += [{"video": video_ref(x)} for x in content.videos]

        parameters = {
            "enable_fusion": True,
            "dimension": self.dimension,
        }
        if instruct:
            parameters["instruct"] = instruct

        data = self.client.post(
            self.PATH,
            {
                "model": self.model,
                "input": {"contents": contents},
                "parameters": parameters,
            },
        )

        embeddings = data.get("output", {}).get("embeddings", [])
        if not embeddings:
            raise RuntimeError("qwen3-vl-embedding returned no vector")

        item = next(
            (x for x in embeddings if x.get("type") in {"fusion", "fused"}),
            embeddings[0],
        )
        vector = item.get("embedding")
        if not isinstance(vector, list):
            raise RuntimeError("invalid embedding response")
        if len(vector) != self.dimension:
            raise RuntimeError(
                f"dimension mismatch: expected {self.dimension}, got {len(vector)}"
            )
        emit("vl.embed", model=self.model, dim=self.dimension, text_parts=len(content.texts))
        return [float(x) for x in vector]
