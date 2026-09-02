import json
import threading

from app.config import Settings
from app.observability.setup import (
    env_flag_disabled,
    load_project_dotenv,
    setup_logging,
    shutdown_logging,
)
from app.observability.sink import TraceSink
from app.observability.trace import bind_turn, emit


def test_emit_writes_jsonl(tmp_path):
    path = setup_logging(source="cli", log_dir=tmp_path, force=True)
    assert path is not None
    bind_turn("abcd1234")
    emit("gate.decided", decision="retrieve", score=0.9, reasons=["history"])
    shutdown_logging()

    text = path.read_text(encoding="utf-8")
    assert "gate.decided" in text
    assert "abcd1234" in text
    assert "retrieve" in text


def test_setup_noop_under_pytest_without_force(tmp_path):
    path = setup_logging(source="cli", log_dir=tmp_path, force=False)
    assert path is None
    emit("should.not.appear", secret="nope")
    files = list(tmp_path.glob("*.jsonl"))
    assert files == []


def test_dotenv_ame_log_disabled_populates_os_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("AME_LOG_DISABLED", raising=False)
    monkeypatch.delenv("LOG_DISABLED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("AME_LOG_DISABLED=1\n", encoding="utf-8")
    load_project_dotenv(path=env_file)
    assert env_flag_disabled()


def test_settings_reads_ame_log_disabled_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("AME_LOG_DISABLED", raising=False)
    monkeypatch.delenv("LOG_DISABLED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("AME_LOG_DISABLED=true\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.log_disabled is True


def test_settings_reads_ame_log_disabled_from_process_env(monkeypatch):
    monkeypatch.setenv("AME_LOG_DISABLED", "1")
    monkeypatch.delenv("LOG_DISABLED", raising=False)
    settings = Settings(_env_file=None)
    assert settings.log_disabled is True


def test_trace_sink_concurrent_writes_are_valid_jsonl(tmp_path):
    jsonl_path = tmp_path / "t.jsonl"
    log_path = tmp_path / "t.log"
    sink = TraceSink(jsonl_path, log_path)
    workers = 4
    per_worker = 50

    def worker(prefix: int) -> None:
        for i in range(per_worker):
            sink.write(
                {
                    "ts": "t",
                    "turn": "1",
                    "event": "x",
                    "payload": {"i": i, "w": prefix},
                }
            )

    threads = [
        threading.Thread(target=worker, args=(n,)) for n in range(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    sink.close()

    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == workers * per_worker
    for line in lines:
        json.loads(line)
