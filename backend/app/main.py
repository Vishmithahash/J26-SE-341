import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.components.c1_tool_call_correctness import router as c1_router
from app.components.c2_state_aware_workflow.api.router import router as c2_router
from app.components.c3_robustness_recovery.api.router import router as c3_router
from app.components.c4_policy_aware_safety.api import router as c4_router
from app.database import engine
from app.health import router as health_router
from app.shared.auth.router import router as shared_auth_router
from app.shared.integration.router import router as shared_integration_router
from app.shared.llm.router import router as shared_llm_router
from app.shared.projects.router import router as shared_projects_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="QA Framework API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS for local frontend development (Vite dev server proxy handles production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error processing request %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database service is temporarily unavailable. Please try again in a few moments."
        },
    )


app.include_router(health_router)
app.include_router(shared_auth_router)
app.include_router(shared_projects_router)
app.include_router(shared_llm_router)
app.include_router(shared_integration_router)
app.include_router(c1_router)
app.include_router(c4_router)
app.include_router(c2_router)
app.include_router(c3_router)
