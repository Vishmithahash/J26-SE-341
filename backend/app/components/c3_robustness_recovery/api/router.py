from collections.abc import Callable

from fastapi import APIRouter, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    FaultGenerationRequest,
    FaultGenerationResponse,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    FaultCatalogResponse,
    FaultValidationRequest,
    FaultValidationResponse,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c3_robustness_recovery.services.validation import (
    get_fault_catalog,
    validate_fault_case,
)


class C3SafeRoute(APIRoute):
    """Custom APIRoute for C3 that sanitizes request validation errors.

    Ensures that raw inputs, request bodies, exception dumps, and Pydantic ctx
    are never echoed back in HTTP 422 responses or logged.
    """

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                sanitized_errors = []
                for err in exc.errors():
                    msg = err.get("msg", "Validation error")
                    # Ensure no raw credentials or exception details are present in messages
                    if "forbidden" in msg.lower() or "credential" in msg.lower():
                        msg = "Input validation failed: invalid or forbidden content."

                    sanitized_errors.append(
                        {
                            "loc": [str(p) for p in err.get("loc", ["body"])],
                            "msg": msg,
                            "type": err.get("type", "value_error"),
                        }
                    )
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content={"detail": sanitized_errors},
                )

        return custom_handler


router = APIRouter(
    prefix="/api/v1/c3",
    tags=["Component 3: Robustness and Failure Recovery"],
    route_class=C3SafeRoute,
)


@router.get(
    "/fault-catalog",
    response_model=FaultCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Operational Fault Families Catalogue",
    description=(
        "Returns the catalogue of the five operational fault families supported by "
        "Component 3. All injection capabilities are currently marked as not implemented."
    ),
)
def fault_catalog() -> FaultCatalogResponse:
    """Return catalogue of operational fault families for static validation."""
    return get_fault_catalog()


@router.post(
    "/cases/validate",
    response_model=FaultValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Candidate Fault Case",
    description=(
        "Performs pure deterministic static validation of a candidate fault case against "
        "an adapter capability manifest, task fixture metadata, and recovery contract. "
        "Returns HTTP 200 with STATIC_VALID or TEST_NOT_READY."
    ),
)
def validate_case(
    request: FaultValidationRequest,
) -> FaultValidationResponse:
    """Validate declared candidate fault case metadata deterministically."""
    return validate_fault_case(request)


@router.post(
    "/cases/generate",
    response_model=FaultGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Feasible Fault Cases and Frozen Suite",
    description=(
        "Performs pure deterministic generation, deduplication, and selection of feasible fault "
        "cases from declared capability combinations and task metadata. Returns a frozen suite "
        "with SHA256 digest and static-only validation scope. No target or runner execution."
    ),
)
def generate_cases(
    request: FaultGenerationRequest,
) -> FaultGenerationResponse:
    """Deterministically generate and freeze feasible fault cases without executing them."""
    return generate_feasible_cases(request)


@router.post(
    "/recovery/evaluate",
    response_model=RecoveryEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Recovery From Evidence and C2 Facts",
    description=(
        "Performs pure deterministic evaluation of recovery rules against frozen contracts, "
        "linked trial evidence, and C2 assertion facts. Returns explainable recovery verdicts "
        "(PASS_COMPLETED, PASS_GRACEFUL, FAIL, INCONCLUSIVE) without target execution."
    ),
)
def evaluate_recovery_endpoint(
    request: RecoveryEvaluationRequest,
) -> RecoveryEvaluationResult:
    """Deterministically evaluate recovery rules from submitted evidence and C2 facts."""
    return evaluate_recovery(request)
