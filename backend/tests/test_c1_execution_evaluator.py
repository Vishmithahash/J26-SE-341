from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    EventStatus,
    ExecutionReasonCode,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
    FieldPresence,
    SourceDataRelationship,
    SourceRelationshipType,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
    FixturePreparationPlan,
    SyntheticRecordRequirement,
)
from app.components.c1_tool_call_correctness.contracts.results import CorrectnessVerdict
from app.components.c1_tool_call_correctness.services.agent_adapter import (
    redact_sensitive_values,
)
from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
    DeterministicCorrectnessEvaluator,
)
from app.components.c1_tool_call_correctness.services.fixture_service import (
    SyntheticFixtureService,
)


def _build_refund_spec() -> ExpectedToolCallSpec:
    return ExpectedToolCallSpec(
        tool_name="issue_refund",
        is_forbidden=False,
        min_count=1,
        max_count=1,
        argument_constraints=[
            ArgumentConstraint(
                argument_path="order_id",
                expected_presence=FieldPresence.REQUIRED_NON_NULL,
                operator=ComparisonOperator.EQUALS,
                expected_value="ord_9901",
            ),
            ArgumentConstraint(
                argument_path="amount",
                expected_presence=FieldPresence.REQUIRED_NON_NULL,
                operator=ComparisonOperator.EQUALS,
                expected_value=42.50,
            ),
            ArgumentConstraint(
                argument_path="customer_id",
                expected_presence=FieldPresence.REQUIRED_NON_NULL,
                source_relationship=SourceDataRelationship(
                    source_record_id="cus_101",
                    source_path="id",
                    relationship_type=SourceRelationshipType.EXACT_MATCH,
                ),
            ),
        ],
    )


def test_evaluator_correct_refund_call():
    """Scenario 1: Correct tool selection, argument values, and contextual source binding -> PASS."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101", "name": "Alice"}}

    events = [
        CapturedToolEvent(
            event_id="evt_01",
            call_index=0,
            tool_name="issue_refund",
            arguments={
                "order_id": "ord_9901",
                "amount": 42.50,
                "customer_id": "cus_101",
            },
            status=EventStatus.SUCCESS,
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_01",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.PASS
    assert all(c.verdict == CorrectnessVerdict.PASS for c in checks)


def test_evaluator_wrong_tool_forbidden_invoked():
    """Scenario 2: Forbidden tool was invoked -> FAIL."""
    evaluator = DeterministicCorrectnessEvaluator()
    forbidden_spec = ExpectedToolCallSpec(
        tool_name="delete_order",
        is_forbidden=True,
        min_count=0,
        max_count=0,
    )

    events = [
        CapturedToolEvent(
            event_id="evt_02",
            call_index=0,
            tool_name="delete_order",
            arguments={"order_id": "ord_9901"},
            status=EventStatus.SUCCESS,
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_02",
        category=CaseCategory.WRONG_TOOL_SELECTION,
        resolved_expectations=[forbidden_spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data={},
        requirement_refs=["REQ-FORBIDDEN-01"],
    )

    assert verdict == CorrectnessVerdict.FAIL
    forbid_check = next(c for c in checks if c.target_tool == "delete_order")
    assert forbid_check.verdict == CorrectnessVerdict.FAIL
    assert forbid_check.reason_code == ExecutionReasonCode.FORBIDDEN_TOOL_INVOKED.value


def test_evaluator_missing_argument():
    """Scenario 3: Missing required argument 'amount' -> FAIL."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101"}}

    # Omit amount completely
    events = [
        CapturedToolEvent(
            event_id="evt_03",
            call_index=0,
            tool_name="issue_refund",
            arguments={"order_id": "ord_9901", "customer_id": "cus_101"},
            status=EventStatus.SUCCESS,
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_03",
        category=CaseCategory.MISSING_ARGUMENTS,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.FAIL
    amount_check = next(c for c in checks if c.target_argument == "amount")
    assert amount_check.verdict == CorrectnessVerdict.FAIL
    assert amount_check.reason_code == ExecutionReasonCode.ARGUMENT_MISSING.value


def test_evaluator_incorrect_argument_value():
    """Scenario 4: Value mismatch on amount -> FAIL."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101"}}

    events = [
        CapturedToolEvent(
            event_id="evt_04",
            call_index=0,
            tool_name="issue_refund",
            arguments={
                "order_id": "ord_9901",
                "amount": 999.00,  # Expected 42.50
                "customer_id": "cus_101",
            },
            status=EventStatus.SUCCESS,
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_04",
        category=CaseCategory.INCORRECT_ARGUMENT_VALUES,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.FAIL
    amount_check = next(c for c in checks if c.target_argument == "amount")
    assert amount_check.verdict == CorrectnessVerdict.FAIL
    assert amount_check.reason_code == ExecutionReasonCode.ARGUMENT_VALUE_MISMATCH.value


def test_evaluator_source_record_mismatch():
    """Scenario 5: Contextual source mismatch on customer_id -> FAIL."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101"}}

    events = [
        CapturedToolEvent(
            event_id="evt_05",
            call_index=0,
            tool_name="issue_refund",
            arguments={
                "order_id": "ord_9901",
                "amount": 42.50,
                "customer_id": "cus_stranger_999",  # Does not match Alice's id cus_101
            },
            status=EventStatus.SUCCESS,
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_05",
        category=CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.FAIL
    cus_check = next(c for c in checks if c.target_argument == "customer_id")
    assert cus_check.verdict == CorrectnessVerdict.FAIL
    assert cus_check.reason_code == ExecutionReasonCode.SOURCE_VALUE_MISMATCH.value


def test_evaluator_explicit_null_argument():
    """Scenario 6: Argument passed as explicit None when REQUIRED_NON_NULL -> FAIL."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101"}}

    events = [
        CapturedToolEvent(
            event_id="evt_06",
            call_index=0,
            tool_name="issue_refund",
            arguments={
                "order_id": "ord_9901",
                "amount": None,  # Explicit null
                "customer_id": "cus_101",
            },
            status=EventStatus.SUCCESS,
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_06",
        category=CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.FAIL
    amount_check = next(c for c in checks if c.target_argument == "amount")
    assert (
        amount_check.reason_code
        == ExecutionReasonCode.ARGUMENT_EXPLICIT_NULL_VIOLATION.value
    )


def test_complete_vs_incomplete_trace_handling():
    """Scenario 7: Incomplete trace must NOT be treated as proof that a tool was never called.
    - Complete trace with missing tool -> FAIL (REQUIRED_TOOL_MISSING)
    - Incomplete trace with missing tool -> INCONCLUSIVE (INCOMPLETE_TRACE_MISSING_TOOL)
    """
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()

    # Case A: Complete trace, 0 calls
    verdict_complete, checks_complete = evaluator.evaluate_case(
        case_id="case_07a",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[spec],
        captured_events=[],
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data={},
        requirement_refs=["REQ-REFUND-01"],
    )
    assert verdict_complete == CorrectnessVerdict.FAIL
    assert (
        checks_complete[0].reason_code
        == ExecutionReasonCode.REQUIRED_TOOL_MISSING.value
    )

    # Case B: Incomplete trace, 0 calls
    verdict_incomplete, checks_incomplete = evaluator.evaluate_case(
        case_id="case_07b",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[spec],
        captured_events=[],
        trace_completeness=TraceCompleteness.INCOMPLETE,
        context_data={},
        requirement_refs=["REQ-REFUND-01"],
    )
    assert verdict_incomplete == CorrectnessVerdict.INCONCLUSIVE
    assert (
        checks_incomplete[0].reason_code
        == ExecutionReasonCode.INCOMPLETE_TRACE_MISSING_TOOL.value
    )


def test_evaluator_failed_tool_call():
    """Scenario 8: Tool call returned runtime error (status=FAILED) -> FAIL."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101"}}

    events = [
        CapturedToolEvent(
            event_id="evt_08",
            call_index=0,
            tool_name="issue_refund",
            arguments={
                "order_id": "ord_9901",
                "amount": 42.50,
                "customer_id": "cus_101",
            },
            status=EventStatus.FAILED,
            tool_error="Payment gateway returned 503 Service Unavailable",
        )
    ]

    verdict, checks = evaluator.evaluate_case(
        case_id="case_08",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.FAIL
    status_check = next(c for c in checks if c.rule_name == "TOOL_EXECUTION_STATUS")
    assert status_check.verdict == CorrectnessVerdict.FAIL
    assert status_check.reason_code == ExecutionReasonCode.CALL_EXECUTION_FAILED.value


def test_insufficient_evidence_safe_refusal():
    """An agent safely refusing to invoke tools when evidence is insufficient satisfies the requirement."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()

    verdict, checks = evaluator.evaluate_case(
        case_id="case_insufficient",
        category=CaseCategory.INSUFFICIENT_EVIDENCE,
        resolved_expectations=[spec],
        captured_events=[],  # Agent made 0 calls
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data={},
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict == CorrectnessVerdict.PASS
    assert (
        checks[0].reason_code
        == ExecutionReasonCode.INSUFFICIENT_EVIDENCE_SATISFIED.value
    )


def test_replaying_identical_evidence_deterministic_verdict():
    """Replaying identical evidence against the same evaluator version produces identical verdicts."""
    evaluator = DeterministicCorrectnessEvaluator()
    spec = _build_refund_spec()
    context = {"cus_101": {"id": "cus_101"}}

    events = [
        CapturedToolEvent(
            event_id="evt_rep",
            call_index=0,
            tool_name="issue_refund",
            arguments={
                "order_id": "ord_9901",
                "amount": 42.50,
                "customer_id": "cus_101",
            },
            status=EventStatus.SUCCESS,
        )
    ]

    verdict_1, checks_1 = evaluator.evaluate_case(
        case_id="case_rep",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    verdict_2, checks_2 = evaluator.evaluate_case(
        case_id="case_rep",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[spec],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data=context,
        requirement_refs=["REQ-REFUND-01"],
    )

    assert verdict_1 == verdict_2 == CorrectnessVerdict.PASS
    assert len(checks_1) == len(checks_2)
    for c1, c2 in zip(checks_1, checks_2, strict=True):
        assert c1.verdict == c2.verdict
        assert c1.reason_code == c2.reason_code


def test_fixture_service_isolation_and_reset():
    """Fixture service isolates sessions and prevents leakage upon reset."""
    fixture_service = SyntheticFixtureService()
    plan = FixturePreparationPlan(
        fixture_capability_ref="sql_sandbox",
        synthetic_records=[
            SyntheticRecordRequirement(
                record_id="ord_9901",
                record_type="order",
                attributes={"total_amount": 42.50},
            )
        ],
    )

    session_1 = "sess_001"
    session_2 = "sess_002"

    ok_1, data_1, ev_1 = fixture_service.prepare_fixture(session_1, plan)
    assert ok_1 is True
    assert "ord_9901" in data_1
    assert len(ev_1) == 1
    assert ev_1[0].channel == EvidenceChannel.AUT_DATABASE_DIFF

    # Verify session 2 is initially empty
    assert fixture_service.get_session_data(session_2) is None

    # Reset session 1
    fixture_service.reset_session(session_1)
    assert fixture_service.get_session_data(session_1) is None


def test_secret_redaction_conventions():
    """Sensitive keys must be redacted from captured traces and argument payloads."""
    payload = {
        "order_id": "ord_9901",
        "api_key": "secret_live_live_99999",
        "nested": {
            "auth_token": "bearer 12345",
            "password": "super-secret-password",
            "safe_field": "visible",
        },
    }
    redacted = redact_sensitive_values(payload)
    assert redacted["order_id"] == "ord_9901"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["auth_token"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == "visible"
