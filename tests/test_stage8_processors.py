from multimodal.processors.code import (
    CodeProcessor,
)
from multimodal.processors.markdown import (
    MarkdownProcessor,
)
from multimodal.router import (
    MultimodalRouter,
)
from multimodal.types import Modality


def test_markdown_heading_aware():
    processor = MarkdownProcessor()

    sections = processor.process_text(
        """
# Embedding

Embedding maps text to vectors.

## Vector Search

Vector search retrieves semantic neighbors.
""".strip()
    )

    assert len(sections) == 2
    assert sections[0]["heading"] == "Embedding"
    assert sections[1]["heading"] == "Vector Search"


def test_router_image():
    router = MultimodalRouter()

    plan = router.route(
        "给我找之前 Planner 的架构图"
    )

    assert plan.search_images is True


def test_router_code_identifier():
    router = MultimodalRouter()

    plan = router.route(
        "MemoryManager.update 是怎么实现的"
    )

    assert (
        Modality.CODE
        in plan.artifact_modalities
    )
