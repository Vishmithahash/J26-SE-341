from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK)
def root():
    return {"message": "Agentic AI QA Framework API", "status": "running"}


@router.get("/health", status_code=status.HTTP_200_OK)
def health():
    return {"status": "healthy"}


@router.get("/health/db")
def health_db(db: Annotated[Session, Depends(get_db)]):
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return {"status": "healthy", "database": "connected"}
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "unavailable"},
        )
    except (SQLAlchemyError, Exception):  # noqa: BLE001
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "unavailable"},
        )
