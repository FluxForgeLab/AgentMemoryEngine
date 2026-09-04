"""Offline Stage 10 API smoke against a running Docker service.

Uses stdlib only. Does not call Qwen and does not stop compose volumes.
Default base URL: http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
HEALTH_WAIT_SECONDS = 60


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def request(
    base_url: str,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    expected_status: int = 200,
) -> dict | None:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        fail(f"{method} {path} -> HTTP {exc.code}: {detail}")

    if status != expected_status:
        fail(f"{method} {path} -> HTTP {status}, expected {expected_status}")

    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def wait_for_health(base_url: str) -> dict:
    deadline = time.time() + HEALTH_WAIT_SECONDS
    last_error = "health endpoint not reachable"
    while time.time() < deadline:
        try:
            payload = request(base_url, "GET", "/v1/health")
            if payload and payload.get("status") == "ok":
                return payload
            last_error = f"unexpected health payload: {payload}"
        except SystemExit as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    fail(f"health not ready within {HEALTH_WAIT_SECONDS}s: {last_error}")


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    probe = f"docker-smoke-{int(time.time() * 1000)}"
    content = f"上次 Planner 在 Planning 前增加 Research 阶段 {probe}"

    health = wait_for_health(base_url)
    if health.get("stage") != 10:
        fail(f"health stage={health.get('stage')!r}, expected 10")
    print("PASS GET /v1/health")

    created = request(
        base_url,
        "POST",
        "/v1/memories",
        body={
            "content": content,
            "memory_type": "semantic",
            "importance": 0.9,
            "metadata": {"project": "harness", "probe": probe},
        },
        expected_status=201,
    )
    if not created or not created.get("id"):
        fail(f"create memory missing id: {created}")
    memory_id = created["id"]
    print(f"PASS POST /v1/memories id={memory_id}")

    fetched = request(base_url, "GET", f"/v1/memories/{memory_id}")
    if not fetched or fetched.get("id") != memory_id:
        fail(f"get memory mismatch: {fetched}")
    print("PASS GET /v1/memories/{id}")

    searched = request(
        base_url,
        "POST",
        "/v1/memories/search",
        body={
            "query": content,
            "method": "hybrid",
            "top_k": 5,
            "memory_types": ["semantic"],
            "filters": {"probe": probe},
        },
    )
    results = (searched or {}).get("results") or []
    result_ids = [item.get("id") for item in results]
    if memory_id not in result_ids:
        fail(f"search did not return {memory_id}: {result_ids}")
    print("PASS POST /v1/memories/search")

    prepared = request(
        base_url,
        "POST",
        "/v1/agent/prepare-context",
        body={
            "task": f"继续上次 Planner 随机性问题的设计 {probe}",
            "context": {"project": "harness"},
        },
    )
    required = ("gate_decision", "retrieval_plan", "memories", "memory_context")
    missing = [key for key in required if prepared is None or key not in prepared]
    if missing:
        fail(f"prepare-context missing fields: {missing}")
    print("PASS POST /v1/agent/prepare-context")

    updated = request(
        base_url,
        "PATCH",
        f"/v1/memories/{memory_id}",
        body={"content": f"{content} (patched)"},
    )
    if not updated or updated.get("id") != memory_id:
        fail(f"patch memory mismatch: {updated}")
    if updated.get("content") != f"{content} (patched)":
        fail(f"patch did not update content: {updated.get('content')!r}")
    print("PASS PATCH /v1/memories/{id}")

    request(
        base_url,
        "DELETE",
        f"/v1/memories/{memory_id}",
        expected_status=204,
    )
    print("PASS DELETE /v1/memories/{id}")
    print("Docker smoke PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
