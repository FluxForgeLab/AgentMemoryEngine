from app.api.dependencies import get_agent_harness, get_memory_service
from app.api.health import assess_readiness
from app.config import get_settings


def _isolate_health(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "lance"))
    monkeypatch.setenv("MEMORY_TABLE_NAME", "service_memories")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("RERANKER_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_DIM", "32")
    get_settings.cache_clear()
    get_memory_service.cache_clear()
    get_agent_harness.cache_clear()


def test_live_is_always_ok(tmp_path, monkeypatch):
    _isolate_health(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/v1/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["stage"] == 10
    assert body["check"] == "live"


def test_legacy_health_keeps_smoke_shape(tmp_path, monkeypatch):
    _isolate_health(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "stage": 10}


def test_ready_ok_when_service_and_store_work(tmp_path, monkeypatch):
    _isolate_health(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["stage"] == 10
    assert body["check"] == "ready"
    assert body["service"] == "initialized"
    assert body["storage"] == "writable"
    assert body["embedding"] == "mock"


def test_ready_not_configured_when_qwen_key_missing(tmp_path, monkeypatch):
    _isolate_health(tmp_path, monkeypatch)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "")
    monkeypatch.setenv("BAILIAN_BASE_URL", "")
    get_settings.cache_clear()

    result = assess_readiness()
    assert result.ready is False
    assert result.details["embedding"] == "not_configured"


def test_ready_fails_when_lancedb_path_is_a_file(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    _isolate_health(tmp_path, monkeypatch)
    monkeypatch.setenv("MEMORY_DB_PATH", str(blocked))
    get_settings.cache_clear()
    get_memory_service.cache_clear()

    result = assess_readiness()
    assert result.ready is False
    assert result.details.get("service") == "unavailable" or result.details.get("storage") == "not_writable"
