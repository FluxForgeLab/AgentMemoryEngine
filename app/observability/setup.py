from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from app.observability.sink import NullSink, TraceSink
from app.observability.trace import bind_session, emit, set_sink

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_LOADED = False
_TRUTHY = {"1", "true", "yes", "on"}


def project_root() -> Path:
    return _PROJECT_ROOT


def default_log_dir() -> Path:
    return _PROJECT_ROOT / "logs"


def load_project_dotenv(path: Path | None = None) -> None:
    """Load repo-root `.env` into os.environ. Existing process env wins."""
    global _DOTENV_LOADED
    target = Path(path) if path is not None else _PROJECT_ROOT / ".env"
    if path is None:
        if _DOTENV_LOADED:
            return
        _DOTENV_LOADED = True
    if not target.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(target, override=False)


def env_flag_disabled() -> bool:
    for name in ("AME_LOG_DISABLED", "LOG_DISABLED"):
        if os.getenv(name, "").strip().lower() in _TRUTHY:
            return True
    return False


def logging_disabled(*, force: bool = False) -> bool:
    if force:
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    load_project_dotenv()
    if env_flag_disabled():
        return True
    from app.config import get_settings

    return bool(get_settings().log_disabled)


def setup_logging(
    *,
    source: str,
    log_dir: str | Path | None = None,
    force: bool = False,
) -> Path | None:
    if logging_disabled(force=force):
        set_sink(NullSink())
        bind_session(source=source, session_id="")
        return None

    directory = Path(log_dir) if log_dir else default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_id = f"{source}-{stamp}"
    jsonl_path = directory / f"{session_id}.jsonl"
    log_path = directory / f"{session_id}.log"
    sink = TraceSink(jsonl_path, log_path)
    set_sink(sink)
    bind_session(source=source, session_id=session_id)
    emit("session.start", source=source, jsonl=str(jsonl_path), log=str(log_path))
    return jsonl_path


def shutdown_logging() -> None:
    emit("session.end")
    from app.observability.trace import current_sink

    current_sink().close()
    set_sink(NullSink())
