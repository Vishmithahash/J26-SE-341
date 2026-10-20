import pytest
from pydantic import ValidationError

from app.components.c1_tool_call_correctness.contracts.configuration import (
    CodeMapping,
    ToolDefinition,
    ToolParameterSchema,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ComparisonOperator,
    FieldPresence,
    FieldPresenceState,
    SourceDataRelationship,
    SourceRelationshipType,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CaseVerdictContract,
    CheckLevelResult,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.services.evaluator_rules import (
    evaluate_argument_presence,
    evaluate_operator,
    evaluate_source_relationship,
    extract_path_value,
)


def test_field_presence_state_inspection():
    """Verify distinct inspection of MISSING, EXPLICIT_NULL, and PRESENT_NON_NULL."""
    data = {"present_key": "some_value", "null_key": None}

    assert FieldPresenceState.inspect(data, "missing_key") == FieldPresenceState.MISSING
    assert (
        FieldPresenceState.inspect(data, "null_key") == FieldPresenceState.EXPLICIT_NULL
    )
    assert (
        FieldPresenceState.inspect(data, "present_key")
        == FieldPresenceState.PRESENT_NON_NULL
    )


def test_field_presence_satisfaction_matrix():
    """Verify that presence constraints strictly enforce missing vs null semantics."""
    # REQUIRED_NON_NULL
    assert (
        FieldPresenceState.PRESENT_NON_NULL.satisfies(FieldPresence.REQUIRED_NON_NULL)
        is True
    )
    assert (
        FieldPresenceState.EXPLICIT_NULL.satisfies(FieldPresence.REQUIRED_NON_NULL)
        is False
    )
    assert (
        FieldPresenceState.MISSING.satisfies(FieldPresence.REQUIRED_NON_NULL) is False
    )

    # REQUIRED_EXPLICIT_NULL
    assert (
        FieldPresenceState.EXPLICIT_NULL.satisfies(FieldPresence.REQUIRED_EXPLICIT_NULL)
        is True
    )
    assert (
        FieldPresenceState.PRESENT_NON_NULL.satisfies(
            FieldPresence.REQUIRED_EXPLICIT_NULL
        )
        is False
    )
    assert (
        FieldPresenceState.MISSING.satisfies(FieldPresence.REQUIRED_EXPLICIT_NULL)
        is False
    )

    # REQUIRED_PRESENT (null or non-null, but key must exist)
    assert (
        FieldPresenceState.PRESENT_NON_NULL.satisfies(FieldPresence.REQUIRED_PRESENT)
        is True
    )
    assert (
        FieldPresenceState.EXPLICIT_NULL.satisfies(FieldPresence.REQUIRED_PRESENT)
        is True
    )
    assert FieldPresenceState.MISSING.satisfies(FieldPresence.REQUIRED_PRESENT) is False

    # FORBIDDEN_OR_MISSING
    assert (
        FieldPresenceState.MISSING.satisfies(FieldPresence.FORBIDDEN_OR_MISSING) is True
    )
    assert (
        FieldPresenceState.EXPLICIT_NULL.satisfies(FieldPresence.FORBIDDEN_OR_MISSING)
        is False
    )
    assert (
        FieldPresenceState.PRESENT_NON_NULL.satisfies(
            FieldPresence.FORBIDDEN_OR_MISSING
        )
        is False
    )

    # ALLOWED
    assert FieldPresenceState.MISSING.satisfies(FieldPresence.ALLOWED) is True
    assert FieldPresenceState.EXPLICIT_NULL.satisfies(FieldPresence.ALLOWED) is True
    assert FieldPresenceState.PRESENT_NON_NULL.satisfies(FieldPresence.ALLOWED) is True


def test_evaluate_argument_presence_service():
    args = {"amount": 50.0, "notes": None}

    ok, _ = evaluate_argument_presence(args, "amount", FieldPresence.REQUIRED_NON_NULL)
    assert ok is True

    ok, msg = evaluate_argument_presence(args, "notes", FieldPresence.REQUIRED_NON_NULL)
    assert ok is False
    assert "EXPLICIT_NULL" in msg

    ok, _ = evaluate_argument_presence(
        args, "notes", FieldPresence.REQUIRED_EXPLICIT_NULL
    )
    assert ok is True

    ok, msg = evaluate_argument_presence(
        args, "missing_param", FieldPresence.REQUIRED_PRESENT
    )
    assert ok is False
    assert "MISSING" in msg


def test_verdict_contract_strictly_three_values():
    """Correctness verdicts must be exactly PASS, FAIL, INCONCLUSIVE."""
    assert {v.value for v in CorrectnessVerdict} == {"PASS", "FAIL", "INCONCLUSIVE"}


def test_verdict_invariance_unconfigured_or_unexecuted_cannot_pass():
    """An unconfigured or unexecuted case must never receive a PASS verdict."""
    # Attempting to assign PASS when execution is NOT_EXECUTED must raise ValidationError
    with pytest.raises(ValidationError) as exc:
        CaseVerdictContract(
            project_id="proj_1",
            case_id="case_1",
            run_id="run_1",
            requirement_version="1.0",
            evaluator_version="1.0.0",
            readiness_status=CaseReadinessStatus.CONFIGURED,
            execution_status=CaseExecutionStatus.NOT_EXECUTED,
            verdict=CorrectnessVerdict.PASS,
        )
    assert "unexecuted case" in str(exc.value)

    # Attempting to assign PASS when readiness is UNCONFIGURED must raise ValidationError
    with pytest.raises(ValidationError) as exc:
        CaseVerdictContract(
            project_id="proj_1",
            case_id="case_1",
            run_id="run_1",
            requirement_version="1.0",
            evaluator_version="1.0.0",
            readiness_status=CaseReadinessStatus.UNCONFIGURED,
            execution_status=CaseExecutionStatus.EXECUTED,
            verdict=CorrectnessVerdict.PASS,
        )
    assert "unconfigured case" in str(exc.value)

    # Valid PASS case when both CONFIGURED and EXECUTED
    contract = CaseVerdictContract(
        project_id="proj_1",
        case_id="case_1",
        run_id="run_1",
        requirement_version="1.0",
        evaluator_version="1.0.0",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.PASS,
        check_results=[
            CheckLevelResult(
                check_id="chk_1",
                rule_name="order_id_matches",
                verdict=CorrectnessVerdict.PASS,
                explanation="Observed order_id matches expected source record",
            )
        ],
    )
    assert contract.verdict == CorrectnessVerdict.PASS


def test_source_code_access_is_optional():
    """Source code mapping must remain strictly optional across contracts."""
    tool_no_code = ToolDefinition(
        name="simple_tool",
        description="Tool without repository code mapping",
        parameters_schema=ToolParameterSchema(),
    )
    assert tool_no_code.code_mapping is None

    tool_with_code = ToolDefinition(
        name="mapped_tool",
        description="Tool with code mapping",
        code_mapping=CodeMapping(
            file_path="src/tools/refund.py",
            function_name="issue_refund",
            line_start=15,
            line_end=42,
        ),
    )
    assert tool_with_code.code_mapping.function_name == "issue_refund"


def test_bounded_declarative_operators():
    """Verify bounded comparison operators without arbitrary code execution."""
    assert evaluate_operator(ComparisonOperator.EQUALS, 42, 42)[0] is True
    assert evaluate_operator(ComparisonOperator.EQUALS, "abc", "xyz")[0] is False
    assert evaluate_operator(ComparisonOperator.GREATER_THAN, 100, 50)[0] is True
    assert evaluate_operator(ComparisonOperator.LESS_EQUAL, 50, 50)[0] is True
    assert (
        evaluate_operator(ComparisonOperator.IN_SET, "blue", ["red", "blue", "green"])[
            0
        ]
        is True
    )
    assert (
        evaluate_operator(ComparisonOperator.REGEX_MATCH, "ORD-9821", r"^ORD-\d{4}$")[0]
        is True
    )
    assert (
        evaluate_operator(ComparisonOperator.STARTS_WITH, "REF_123", "REF_")[0] is True
    )
    assert evaluate_operator(ComparisonOperator.TYPE_EQUALS, 42.5, "number")[0] is True
    assert (
        evaluate_operator(ComparisonOperator.TYPE_EQUALS, True, "integer")[0] is False
    )


def test_source_data_relationship_evaluation():
    context_data = {
        "fixture_01": {
            "order": {
                "id": "ORD-77",
                "total": 85.50,
                "customer": "ALICE",
            }
        }
    }

    # Test nested path extraction
    found, val = extract_path_value(context_data["fixture_01"], "order.total")
    assert found is True
    assert val == 85.50

    # Test exact match
    rel_exact = SourceDataRelationship(
        source_record_id="fixture_01",
        source_path="order.id",
        relationship_type=SourceRelationshipType.EXACT_MATCH,
    )
    ok, _ = evaluate_source_relationship("ORD-77", context_data, rel_exact)
    assert ok is True

    # Test case-insensitive match
    rel_case = SourceDataRelationship(
        source_record_id="fixture_01",
        source_path="order.customer",
        relationship_type=SourceRelationshipType.CASE_INSENSITIVE_MATCH,
    )
    ok, _ = evaluate_source_relationship("alice", context_data, rel_case)
    assert ok is True

    # Test numeric tolerance
    rel_num = SourceDataRelationship(
        source_record_id="fixture_01",
        source_path="order.total",
        relationship_type=SourceRelationshipType.NUMERIC_TOLERANCE,
        tolerance=0.01,
    )
    ok, _ = evaluate_source_relationship(85.505, context_data, rel_num)
    assert ok is True
    ok, _ = evaluate_source_relationship(86.00, context_data, rel_num)
    assert ok is False
