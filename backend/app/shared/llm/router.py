"""API endpoints for provider discovery, selection management, and connectivity verification."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User
from app.shared.llm.contracts import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    ModelSelectionConfig,
    ProviderStatusInfo,
)
from app.shared.llm.service import LLMProviderService

router = APIRouter(
    prefix="/api/v1/llm",
    tags=["Shared LLM Integration"],
)

_service_instance: LLMProviderService | None = None


def get_llm_service() -> LLMProviderService:
    global _service_instance
    if _service_instance is None:
        _service_instance = LLMProviderService()
    return _service_instance


def set_llm_service(service: LLMProviderService | None) -> None:
    """Dependency override helper for unit tests."""
    global _service_instance
    _service_instance = service


@router.get(
    "/providers",
    response_model=list[ProviderStatusInfo],
    summary="List available/configured LLM providers and models",
)
async def list_providers(
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[LLMProviderService, Depends(get_llm_service)],
) -> list[ProviderStatusInfo]:
    """Retrieve operational status for Local (Ollama) and Hosted (Gemini) providers."""
    return await service.get_providers_status(db=db, user_id=current_user.id)


@router.get(
    "/selection",
    response_model=ModelSelectionConfig,
    summary="Get authenticated user's model selection",
)
def get_user_selection(
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[LLMProviderService, Depends(get_llm_service)],
) -> ModelSelectionConfig:
    """Retrieve the current user's authoritative model selection."""
    selection = service.get_user_selection(current_user.id, db)
    return ModelSelectionConfig(**selection.to_config())


@router.put(
    "/selection",
    response_model=ModelSelectionConfig,
    summary="Update authenticated user's model selection",
)
def update_user_selection(
    payload: ModelSelectionConfig,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[LLMProviderService, Depends(get_llm_service)],
) -> ModelSelectionConfig:
    """Save/activate the user's provider and model choice in persistent storage."""
    try:
        updated = service.save_user_selection(current_user.id, payload, db)
        return ModelSelectionConfig(**updated.to_config())
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.post(
    "/test-connection",
    response_model=ConnectionTestResponse,
    summary="Run bounded inference connectivity probe",
)
async def test_connection(
    payload: ConnectionTestRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[LLMProviderService, Depends(get_llm_service)],
) -> ConnectionTestResponse:
    """Run an explicit, bounded test inference to verify provider and credentials."""
    try:
        return await service.test_connection(
            user_id=current_user.id,
            provider_name=payload.provider,
            model_id=payload.model_id,
            db=db,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
