from enum import Enum

from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationIssue(BaseModel):
    code: str = Field(
        ..., description="Machine-readable rule code, e.g. ERR_MISSING_REQ_REF"
    )
    severity: ValidationSeverity = Field(..., description="Issue severity level")
    message: str = Field(
        ..., description="Human-readable explanation of the validation failure"
    )
    path: str = Field(
        ..., description="Dotted or indexed JSON path to the erroneous element"
    )
    requirement_ref: str | None = Field(
        default=None, description="Associated requirement identifier, if any"
    )


class ValidationSummary(BaseModel):
    is_valid: bool = Field(..., description="True if no ERROR severity issues exist")
    error_count: int = Field(
        default=0, description="Total count of ERROR severity issues"
    )
    warning_count: int = Field(
        default=0, description="Total count of WARNING severity issues"
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list, description="Detailed validation findings"
    )
