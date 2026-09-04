"""Prove LanceDB named volume survives `docker compose down` (without -v).

Uses stdlib only. Drives Docker via the `docker` CLI so it runs on Windows
and Linux. Never passes `-v` / `--volumes` to compose down.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
HEALTH_WAIT_SECONDS = 60
ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (
    "docker",
    "compose",
    "-f",
    str(ROOT / "docker-compose.yml"),
    "-f",
    str(ROOT / "docker-compose.mock.yml"),
)


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


def compose(*args: str) -> None:
    if "-v" in args or "--volumes" in args:
        fail("refusing to run compose with volume wipe")
    cmd = [*COMPOSE, *args]
    print("+", " ".join(cmd))
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        fail(f"{' '.join(cmd)} exited {completed.returncode}: {detail}")
    if completed.stdout.strip():
        print(completed.stdout.rstrip())


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    probe = f"docker-persist-{int(time.time() * 1000)}"
    content = f"persistence probe {probe}"

    compose("up", "-d")
    wait_for_health(base_url)

    created = request(
        base_url,
        "POST",
        "/v1/memories",
        body={
            "content": content,
            "memory_type": "semantic",
            "importance": 0.9,
            "metadata": {"probe": probe},
        },
        expected_status=201,
    )
    if not created or not created.get("id"):
        fail(f"create memory missing id: {created}")
    memory_id = created["id"]
    print(f"wrote memory id={memory_id} probe={probe}")

    compose("down")
    compose("up", "-d")
    wait_for_health(base_url)

    fetched = request(base_url, "GET", f"/v1/memories/{memory_id}")
    if not fetched or fetched.get("id") != memory_id:
        fail(f"memory {memory_id} missing after compose down/up: {fetched}")
    if (fetched.get("metadata") or {}).get("probe") != probe:
        fail(f"probe mismatch after restart: {fetched.get('metadata')}")

    print("Volume persistence PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
