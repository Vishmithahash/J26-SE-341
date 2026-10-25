from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    GeneratedCandidateCase,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationIssue,
    ValidationSeverity,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)


def validate_candidate_case(
    candidate: GeneratedCandidateCase, config: C1ProjectConfigModel
) -> list[ValidationIssue]:
    """Validates a generated candidate case against project configuration metadata.
    Detects schema mismatches, missing references, contradictory constraints,
    evidence capability gaps, and ambiguity.
    """
    issues: list[ValidationIssue] = []

    # 1. Base identity and wording checks
    if not candidate.agent_task_prompt.strip():
        issues.append(
            ValidationIssue(
                code="ERR_EMPTY_TASK_PROMPT",
                severity=ValidationSeverity.ERROR,
                message="agent_task_prompt must not be empty.",
                path=f"candidates[{candidate.case_id}].agent_task_prompt",
            )
        )

    # 2. Requirement reference validation
    declared_req_ids = {
        r.get("req_id") for r in (config.requirements or []) if isinstance(r, dict)
    }
    if (
        not candidate.requirement_refs
        and candidate.category != CaseCategory.INSUFFICIENT_EVIDENCE
    ):
        issues.append(
            ValidationIssue(
                code="ERR_MISSING_REQUIREMENT_REFS",
                severity=ValidationSeverity.ERROR,
                message="Candidate case must reference at least one task requirement.",
                path=f"candidates[{candidate.case_id}].requirement_refs",
            )
        )
    for rref in candidate.requirement_refs:
        if rref not in declared_req_ids:
            issues.append(
                ValidationIssue(
                    code="ERR_UNRESOLVED_REQUIREMENT",
                    severity=ValidationSeverity.ERROR,
                    message=f"Requirement '{rref}' is not declared in project configuration.",
                    path=f"candidates[{candidate.case_id}].requirement_refs",
                    requirement_ref=rref,
                )
            )

    # 3. Tool reference and schema compatibility
    declared_tools: dict[str, dict[str, Any]] = {}
    for t in config.tools or []:
        if isinstance(t, dict) and "name" in t:
            declared_tools[t["name"]] = t

    for idx, expected_call in enumerate(candidate.expected_tool_calls):
        tname = expected_call.tool_name
        tool_path = f"candidates[{candidate.case_id}].expected_tool_calls[{idx}]"

        # Check if tool is known
        if tname not in declared_tools:
            issues.append(
                ValidationIssue(
                    code="ERR_UNSUPPORTED_TOOL",
                    severity=ValidationSeverity.ERROR,
                    message=f"Target tool '{tname}' is not declared in project tool definitions.",
                    path=f"{tool_path}.tool_name",
                )
            )
            continue

        tool_meta = declared_tools[tname]
        params_schema = tool_meta.get("parameters_schema", {})
        schema_props = (
            params_schema.get("properties", {})
            if isinstance(params_schema, dict)
            else {}
        )

        # Contradictory constraints: tool cannot be required and forbidden simultaneously
        if expected_call.is_forbidden and expected_call.min_count > 0:
            issues.append(
                ValidationIssue(
                    code="ERR_CONTRADICTORY_CONSTRAINT",
                    severity=ValidationSeverity.ERROR,
                    message=f"Tool '{tname}' cannot have both is_forbidden=True and min_count > 0.",
                    path=f"{tool_path}",
                )
            )

        # Check argument constraints against tool parameter schema
        for c_idx, arg_con in enumerate(expected_call.argument_constraints):
            arg_name = arg_con.argument_name
            arg_path = f"{tool_path}.argument_constraints[{c_idx}]"

            # Ambiguity check: argument name must not be blank
            if not arg_name.strip():
                issues.append(
                    ValidationIssue(
                        code="ERR_AMBIGUOUS_EXPECTATION",
                        severity=ValidationSeverity.ERROR,
                        message="Argument constraint has blank argument_name.",
                        path=f"{arg_path}.argument_name",
                    )
                )
                continue

            # Check if argument property exists in schema
            if arg_name not in schema_props and not params_schema.get(
                "additional_properties", False
            ):
                issues.append(
                    ValidationIssue(
                        code="ERR_SCHEMA_MISMATCH",
                        severity=ValidationSeverity.ERROR,
                        message=f"Argument '{arg_name}' is not declared in parameters schema for tool '{tname}'.",
                        path=f"{arg_path}.argument_name",
                    )
                )

            # Check type compatibility if expected_type is provided
            if arg_con.expected_type and arg_name in schema_props:
                declared_type = schema_props[arg_name].get("type")
                if declared_type:
                    type_compat = {
                        "string": ["string", "str"],
                        "number": ["number", "float", "integer", "int"],
                        "integer": ["integer", "int", "number"],
                        "boolean": ["boolean", "bool"],
                        "object": ["object", "dict"],
                        "array": ["array", "list"],
                    }
                    # JSON Schema allows a list of types, e.g. ["string", "null"].
                    declared_types = (
                        declared_type
                        if isinstance(declared_type, list)
                        else [declared_type]
                    )
                    allowed = [
                        a for t in declared_types for a in type_compat.get(t, [t])
                    ]
                    if arg_con.expected_type.lower() not in allowed:
                        issues.append(
                            ValidationIssue(
                                code="ERR_SCHEMA_TYPE_MISMATCH",
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Argument '{arg_name}' expected type '{arg_con.expected_type}' "
                                    f"conflicts with declared schema type '{declared_type}'."
                                ),
                                path=f"{arg_path}.expected_type",
                            )
                        )

    # 4. Fixture plan and capability validation
    fixture_refs = config.synthetic_fixture_refs or []
    plan = candidate.fixture_plan
    if plan.fixture_capability_ref not in fixture_refs and fixture_refs:
        issues.append(
            ValidationIssue(
                code="ERR_UNRESOLVED_FIXTURE_REF",
                severity=ValidationSeverity.ERROR,
                message=(
                    f"Fixture plan references '{plan.fixture_capability_ref}', "
                    f"which is not in project declared fixtures {fixture_refs}."
                ),
                path=f"candidates[{candidate.case_id}].fixture_plan.fixture_capability_ref",
            )
        )

    # 5. Evidence capability availability
    declared_trace_channels = {
        tc.get("channel")
        for tc in (config.trace_capabilities or [])
        if isinstance(tc, dict) and tc.get("enabled", True)
    }

    for expected_call in candidate.expected_tool_calls:
        for ev_req in expected_call.evidence_requirements:
            ch_str = (
                ev_req.channel.value
                if isinstance(ev_req.channel, EvidenceChannel)
                else str(ev_req.channel)
            )
            if ch_str not in declared_trace_channels:
                issues.append(
                    ValidationIssue(
                        code="ERR_UNAVAILABLE_EVIDENCE",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Required evidence channel '{ch_str}' is not active "
                            f"in project configuration trace capabilities."
                        ),
                        path=f"candidates[{candidate.case_id}].evidence_requirements",
                    )
                )

    # 6. Specific validation for INSUFFICIENT_EVIDENCE cases
    if candidate.category == CaseCategory.INSUFFICIENT_EVIDENCE and (
        not candidate.evidence_limitations or not candidate.evidence_limitations.strip()
    ):
        issues.append(
            ValidationIssue(
                code="ERR_MISSING_EVIDENCE_LIMITATION",
                severity=ValidationSeverity.ERROR,
                message="Insufficient-evidence cases must explicitly document their evidence limitations.",
                path=f"candidates[{candidate.case_id}].evidence_limitations",
            )
        )

    return issues
