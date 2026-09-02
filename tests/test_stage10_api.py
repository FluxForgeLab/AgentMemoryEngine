from app.api.dependencies import get_agent_harness, get_memory_service
from app.config import get_settings


def _isolate_service(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "lance"))
    monkeypatch.setenv("MEMORY_TABLE_NAME", "service_memories")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("RERANKER_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_DIM", "32")
    get_settings.cache_clear()
    get_memory_service.cache_clear()
    get_agent_harness.cache_clear()


def test_prepare_context_skips_stateless_task(tmp_path, monkeypatch):
    _isolate_service(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/v1/agent/prepare-context",
        json={"task": "1 + 1 等于多少"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gate_decision"]["decision"] == "skip"
    assert body["retrieval_plan"]["should_retrieve"] is False
    assert body["memories"] == []
    assert body["memory_context"] == ""


def test_prepare_context_retrieves_history_task(tmp_path, monkeypatch):
    _isolate_service(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    created = client.post(
        "/v1/memories",
        json={
            "content": "上次 Planner 随机性来自缺少 Research 阶段",
            "memory_type": "reflection",
            "importance": 0.95,
            "metadata": {"project": "harness", "agent": "planner"},
        },
    )
    assert created.status_code == 201

    response = client.post(
        "/v1/agent/prepare-context",
        json={
            "task": "之前 Planner 为什么失败？",
            "context": {"project": "harness", "agent": "planner"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gate_decision"]["decision"] == "retrieve"
    assert body["retrieval_plan"]["should_retrieve"] is True
    assert body["retrieval_plan"]["method"] in {"keyword", "vector", "hybrid", "agentic"}
    assert body["memories"]
    assert "Relevant historical memory" in body["memory_context"]
