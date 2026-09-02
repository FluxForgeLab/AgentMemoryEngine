from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request

from app.api.dependencies import get_memory_service
from app.api.routes import router
from app.config import get_settings
from app.observability.setup import setup_logging, shutdown_logging
from app.observability.trace import bind_turn, emit, reset_context

_SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/favicon.ico")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    setup_logging(source="http", log_dir=settings.log_dir or None)
    try:
        get_memory_service()
        yield
    finally:
        shutdown_logging()


app = FastAPI(
    title="Agent Memory Engine - Stage 10",
    version="0.10.0",
    description="RetrieveGate + RetrievalPlanner + SearchRouter",
    lifespan=lifespan,
)

app.include_router(router)


@app.middleware("http")
async def trace_http(request: Request, call_next):
    path = request.url.path
    if path == "/v1/health" or any(path.startswith(p) for p in _SKIP_PREFIXES):
        return await call_next(request)

    turn = request.headers.get("x-request-id") or bind_turn()
    bind_turn(turn)
    started = time.perf_counter()
    emit("http.request", method=request.method, path=path)
    try:
        response = await call_next(request)
        emit(
            "http.response",
            method=request.method,
            path=path,
            status=response.status_code,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        return response
    except Exception as exc:
        emit(
            "http.response",
            method=request.method,
            path=path,
            status=500,
            error_type=type(exc).__name__,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        raise
    finally:
        reset_context()
