from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dependencies import get_memory_service
from app.api.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_memory_service()
    yield


app = FastAPI(
    title="Agent Memory Engine - Stage 10",
    version="0.10.0",
    description="RetrieveGate + RetrievalPlanner + SearchRouter",
    lifespan=lifespan,
)

app.include_router(router)
