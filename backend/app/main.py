from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.components.c4_policy_aware_safety.api import router as c4_router
from app.database import engine
from app.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="Agentic AI QA Framework API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(health_router)
app.include_router(c4_router)
