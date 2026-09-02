from app.api.dependencies import get_memory_service
from app.config import get_settings


def test_create_and_search_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "lance"))
    monkeypatch.setenv("MEMORY_TABLE_NAME", "service_memories")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("RERANKER_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_DIM", "32")
    get_settings.cache_clear()
    get_memory_service.cache_clear()

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    health = client.get("/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    created = client.post(
        "/v1/memories",
        json={
            "content": "Planner 在 Planning 前增加 Research 阶段",
            "memory_type": "reflection",
            "importance": 0.9,
            "metadata": {"project": "harness"},
        },
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]

    searched = client.post(
        "/v1/memories/search",
        json={
            "query": "为什么 Planner 需要 Research 阶段？",
            "top_k": 5,
            "memory_types": ["reflection"],
            "filters": {"project": "harness"},
            "rerank": True,
        },
    )
    assert searched.status_code == 200
    results = searched.json()["results"]
    assert results
    assert results[0]["id"] == memory_id
