from __future__ import annotations

import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

_TZ = timezone(timedelta(hours=8))


class TraceSink:
    def __init__(self, jsonl_path: Path, log_path: Path):
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = jsonl_path
        self.log_path = log_path
        self._jsonl = jsonl_path.open("a", encoding="utf-8")
        self._log = log_path.open("a", encoding="utf-8")
        self._lock = threading.Lock()
        self.disabled = False

    def write(self, record: dict[str, Any]) -> None:
        if self.disabled:
            return
        jsonl_line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        log_line = _format_line(record) + "\n"
        with self._lock:
            self._jsonl.write(jsonl_line)
            self._jsonl.flush()
            self._log.write(log_line)
            self._log.flush()

    def close(self) -> None:
        with self._lock:
            for handle in (self._jsonl, self._log):
                try:
                    handle.close()
                except Exception:
                    pass


class NullSink:
    disabled = True
    jsonl_path = None
    log_path = None

    def write(self, record: dict[str, Any]) -> None:
        return

    def close(self) -> None:
        return


def now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="milliseconds")


def _format_line(record: dict[str, Any]) -> str:
    event = record.get("event", "")
    turn = record.get("turn", "")
    elapsed = record.get("elapsed_ms")
    suffix = f" {elapsed}ms" if elapsed is not None else ""
    payload = record.get("payload") or {}
    summary = _summary(event, payload)
    return f"{record.get('ts', '')} [{turn}] {event}{suffix}{summary}"


def _summary(event: str, payload: dict[str, Any]) -> str:
    bits = []
    for key in (
        "decision",
        "method",
        "variant",
        "hits",
        "count",
        "path",
        "status",
        "provider",
        "model",
        "sufficient",
        "error_type",
    ):
        if key in payload:
            bits.append(f"{key}={payload[key]}")
    if not bits:
        return ""
    return " " + " ".join(str(x) for x in bits)
