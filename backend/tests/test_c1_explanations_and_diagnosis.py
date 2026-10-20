import asyncio
from pathlib import Path

import pytest

from app.components.c1_tool_call_correctness.contracts.configuration import (
    CodeMapping,
    ToolDefinition,
    ToolParameterSchema,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CauseCategory,
    DiagnosisStatus,
    EvidenceAvailability,
    ExplanationMethod,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    CaseExecutionDetail,
    EventStatus,
    ExecutionReasonCode,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CheckLevelResult,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.services.diagnosis_engine import (
    DiagnosisEngine,
)
from app.components.c1_tool_call_correctness.services.diagnosis_provider import (
    ModelAssistedDiagnosisProvider,
)
from app.components.c1_tool_call_correctness.services.explanation_engine import (
    ExplanationEngine,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    SourceInspectionError,
    SourceInspector,
)


@pytest.fixture
def temp_repo(tmp_path: Path):
    """Creates a temporary mock repository directory with dummy source code files."""
    src_dir = tmp_path / "app"
    src_dir.mkdir(parents=True)

    # 1. App code with argument mapping defect: parameter is 'refund_amount', not 'amount'
    buggy_service = src_dir / "refund_service.py"
    buggy_service.write_text(
        "def process_refund(order_id: str, refund_amount: float, reason: str = ''):\n"
        "    '''Process a customer refund.'''\n"
        "    return {'status': 'processed', 'amount': refund_amount}\n",
        encoding="utf-8",
    )

    # 2. App code with matching signature
    clean_service = src_dir / "clean_service.py"
    clean_service.write_text(
        "def submit_order(order_id: str, items: list):\n"
        "    '''Submit an order.'''\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )

    # 3. Sensitive file
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=supersecret\n", encoding="utf-8")

    return tmp_path


def test_1_real_argument_mapping_code_defect(temp_repo: Path):
    """1. Test that a real argument-mapping defect between tool schema and backend code signature
    is correctly diagnosed as SUPPORTED_APPLICATION_CODE_DEFECT with exact AST code location.
    """
    tool_def = ToolDefinition(
        name="process_refund",
        description="Processes a refund for an order",
        parameters_schema=ToolParameterSchema(
            type="object",
            properties={
                "order_id": {"type": "string"},
                "amount": {"type": "number"},  # Tool schema calls it 'amount'
            },
            required=["order_id", "amount"],
        ),
        code_mapping=CodeMapping(
            file_path="app/refund_service.py",
            function_name="process_refund",
        ),
    )

    # Case execution where agent called the tool or check failed on missing/mismatched argument
    check = CheckLevelResult(
        check_id="chk_refund_arg",
        rule_name="ARGUMENT_PRESENCE_CHECK",
        target_tool="process_refund",
        target_argument="amount",
        verdict=CorrectnessVerdict.FAIL,
        reason_code=ExecutionReasonCode.ARGUMENT_MISSING.value,
        expected_value="PRESENT",
        actual_value="MISSING",
        explanation="Argument 'amount' was missing in tool call.",
        evidence_refs=["ev_ref_1"],
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_001",
        case_id="case_refund_defect",
        attempt_number=1,
        session_id="sess_1",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        captured_events=[
            CapturedToolEvent(
                event_id="evt_01",
                call_index=0,
                tool_name="process_refund",
                arguments={"order_id": "ORD-123"},
                status=EventStatus.SUCCESS,
            )
        ],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )
    assert len(explanations) == 1
    assert explanations[0].tool_name == "process_refund"

    source_inspector = SourceInspector(temp_repo)
    diagnosis_engine = DiagnosisEngine()

    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={"process_refund": tool_def},
        source_inspector=source_inspector,
    )

    assert diag.cause_category == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
    assert len(diag.candidate_code_locations) == 1
    candidate = diag.candidate_code_locations[0]
    assert candidate.file_path == "app/refund_service.py"
    assert candidate.function_name == "process_refund"
    assert candidate.line_start == 1
    assert candidate.line_end == 3
    assert candidate.ranking_score == 1
    assert "discrepancy detected" in candidate.ranking_criteria.lower()
    assert diag.source_hash is not None


def test_2_agent_mistake_with_correct_application_code(temp_repo: Path):
    """2. Test that an agent mistake (e.g. calling forbidden tool or omitting valid param)
    is classified as AGENT_BEHAVIOUR and application code is NEVER blamed.
    """
    tool_def = ToolDefinition(
        name="submit_order",
        description="Submits an order",
        parameters_schema=ToolParameterSchema(
            type="object",
            properties={
                "order_id": {"type": "string"},
                "items": {"type": "array"},
            },
            required=["order_id", "items"],
        ),
        code_mapping=CodeMapping(
            file_path="app/clean_service.py",
            function_name="submit_order",
        ),
    )

    # Agent calls wrong tool 'delete_database' which is forbidden
    check = CheckLevelResult(
        check_id="chk_forbid_delete",
        rule_name="FORBIDDEN_TOOL_CHECK",
        target_tool="delete_database",
        verdict=CorrectnessVerdict.FAIL,
        reason_code=ExecutionReasonCode.FORBIDDEN_TOOL_INVOKED.value,
        expected_value=0,
        actual_value=1,
        explanation="Forbidden tool 'delete_database' was invoked.",
        evidence_refs=["ev_ref_2"],
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_002",
        case_id="case_agent_mistake",
        attempt_number=1,
        session_id="sess_2",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        captured_events=[
            CapturedToolEvent(
                event_id="evt_02",
                call_index=0,
                tool_name="delete_database",
                arguments={},
                status=EventStatus.SUCCESS,
            )
        ],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )

    source_inspector = SourceInspector(temp_repo)
    diagnosis_engine = DiagnosisEngine()

    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={"submit_order": tool_def},
        source_inspector=source_inspector,
    )

    assert diag.cause_category == CauseCategory.AGENT_BEHAVIOUR
    # Application code must NOT be blamed!
    assert len(diag.candidate_code_locations) == 0


def test_3_inconsistent_specification(temp_repo: Path):
    """3. Test that contradictory expectation vs tool schema is diagnosed as
    SPECIFICATION_OR_EXPECTATION_PROBLEM.
    """
    tool_def = ToolDefinition(
        name="submit_order",
        description="Submits an order",
        parameters_schema=ToolParameterSchema(
            type="object",
            properties={
                "order_id": {"type": "string"},
            },
            required=["order_id"],
        ),
    )

    # Expectation requires argument 'secret_override' which tool schema doesn't support
    from app.components.c1_tool_call_correctness.contracts.expectations import (
        ArgumentConstraint,
        ComparisonOperator,
    )

    exp_spec = ExpectedToolCallSpec(
        tool_name="submit_order",
        argument_constraints=[
            ArgumentConstraint(
                argument_name="secret_override",
                operator=ComparisonOperator.EQUALS,
                expected_value="yes",
            )
        ],
    )

    check = CheckLevelResult(
        check_id="chk_spec_incon",
        rule_name="ARGUMENT_PRESENCE_CHECK",
        target_tool="submit_order",
        target_argument="secret_override",
        verdict=CorrectnessVerdict.FAIL,
        reason_code=ExecutionReasonCode.ARGUMENT_MISSING.value,
        expected_value="PRESENT",
        actual_value="MISSING",
        explanation="Argument 'secret_override' missing.",
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_003",
        case_id="case_inconsistent_spec",
        attempt_number=1,
        session_id="sess_3",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        resolved_expectations=[exp_spec],
        captured_events=[
            CapturedToolEvent(
                event_id="evt_03",
                call_index=0,
                tool_name="submit_order",
                arguments={"order_id": "ORD-1"},
            )
        ],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )

    diagnosis_engine = DiagnosisEngine()
    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={"submit_order": tool_def},
        source_inspector=None,
    )

    assert diag.cause_category == CauseCategory.SPECIFICATION_OR_EXPECTATION_PROBLEM
    assert len(diag.candidate_code_locations) == 0


def test_4_missing_source_access():
    """4. Test that when source code access is unavailable, diagnosis proceeds without
    fabricating candidate code locations or line numbers.
    """
    check = CheckLevelResult(
        check_id="chk_req_missing",
        rule_name="REQUIRED_TOOL_CHECK",
        target_tool="lookup_user",
        verdict=CorrectnessVerdict.FAIL,
        reason_code=ExecutionReasonCode.REQUIRED_TOOL_MISSING.value,
        expected_value=1,
        actual_value=0,
        explanation="Required tool was not invoked.",
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_004",
        case_id="case_no_source",
        attempt_number=1,
        session_id="sess_4",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        captured_events=[],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )

    diagnosis_engine = DiagnosisEngine()
    # Explicitly source_inspector=None
    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={},
        source_inspector=None,
    )

    assert diag.cause_category == CauseCategory.AGENT_BEHAVIOUR
    assert diag.candidate_code_locations == []
    assert diag.source_hash is None


def test_5_unsupported_code_location_suggestions(temp_repo: Path):
    """5. Test that when evidence is insufficient to localize a code defect,
    the system returns empty candidate lists rather than guessing or hallucinating locations.
    """
    tool_def = ToolDefinition(
        name="unknown_backend_tool",
        description="Tool with no code mapping",
        parameters_schema=ToolParameterSchema(),
        code_mapping=None,  # No code mapping available
    )

    check = CheckLevelResult(
        check_id="chk_unknown_tool",
        rule_name="ARGUMENT_VALUE_CHECK",
        target_tool="unknown_backend_tool",
        target_argument="token",
        verdict=CorrectnessVerdict.FAIL,
        reason_code=ExecutionReasonCode.ARGUMENT_VALUE_MISMATCH.value,
        expected_value="XYZ",
        actual_value="ABC",
        explanation="Argument mismatch.",
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_005",
        case_id="case_unsupported",
        attempt_number=1,
        session_id="sess_5",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        captured_events=[],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )

    source_inspector = SourceInspector(temp_repo)
    diagnosis_engine = DiagnosisEngine()

    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={"unknown_backend_tool": tool_def},
        source_inspector=source_inspector,
    )

    # Returns empty candidates without guessing
    assert diag.candidate_code_locations == []


def test_6_ambiguous_or_incomplete_evidence():
    """6. Test that incomplete traces or missing evidence are classified as UNKNOWN
    and do not become fabricated mismatches or blamed on code.
    """
    check = CheckLevelResult(
        check_id="chk_incomplete",
        rule_name="REQUIRED_TOOL_CHECK",
        target_tool="process_payment",
        verdict=CorrectnessVerdict.INCONCLUSIVE,
        reason_code=ExecutionReasonCode.INCOMPLETE_TRACE_MISSING_TOOL.value,
        explanation="Trace was truncated.",
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_006",
        case_id="case_incomplete_trace",
        attempt_number=1,
        session_id="sess_6",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.INCONCLUSIVE,
        trace_completeness=TraceCompleteness.INCOMPLETE,
        captured_events=[],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )

    assert len(explanations) == 1
    assert explanations[0].evidence_availability in (
        EvidenceAvailability.PARTIAL,
        EvidenceAvailability.INSUFFICIENT,
    )
    assert len(explanations[0].uncertainties) > 0

    diagnosis_engine = DiagnosisEngine()
    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={},
        source_inspector=None,
    )

    assert diag.cause_category == CauseCategory.UNKNOWN
    assert diag.status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert diag.candidate_code_locations == []


def test_7_stale_source_versions(temp_repo: Path):
    """7. Test that stale source versions or git_ref mismatches record explicit uncertainties."""
    tool_def = ToolDefinition(
        name="process_refund",
        description="Processes a refund for an order",
        parameters_schema=ToolParameterSchema(
            type="object",
            properties={"amount": {"type": "number"}},
            required=["amount"],
        ),
        code_mapping=CodeMapping(
            file_path="app/refund_service.py",
            function_name="process_refund",
            git_ref="v1.0.0",
        ),
    )

    check = CheckLevelResult(
        check_id="chk_refund_arg",
        rule_name="ARGUMENT_PRESENCE_CHECK",
        target_tool="process_refund",
        target_argument="amount",
        verdict=CorrectnessVerdict.FAIL,
        reason_code=ExecutionReasonCode.ARGUMENT_MISSING.value,
        expected_value="PRESENT",
        actual_value="MISSING",
        explanation="Missing amount.",
    )

    case_exec = CaseExecutionDetail(
        execution_id="exec_007",
        case_id="case_stale_version",
        attempt_number=1,
        session_id="sess_7",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        captured_events=[],
        check_results=[check],
    )

    explanation_engine = ExplanationEngine()
    explanations = explanation_engine.explain_case_checks(
        check_results=case_exec.check_results,
        captured_events=case_exec.captured_events,
        trace_completeness=case_exec.trace_completeness,
    )

    source_inspector = SourceInspector(temp_repo)
    diagnosis_engine = DiagnosisEngine()

    diag = diagnosis_engine.diagnose_case(
        project_id="proj_1",
        run_id="run_1",
        case_execution=case_exec,
        check_explanations=explanations,
        tool_definitions={"process_refund": tool_def},
        source_inspector=source_inspector,
        expected_code_version="v2.0.0",  # Mismatch with mapping's v1.0.0!
    )

    assert len(diag.candidate_code_locations) == 1
    cand = diag.candidate_code_locations[0]
    assert any("does not match run code version" in u for u in cand.uncertainties)


def test_8_provider_failure_and_model_assisted_fallback():
    """8. Test that model-assisted provider failures or hallucinated evidence IDs
    gracefully fall back to deterministic results without crashing.
    """
    from app.components.c1_tool_call_correctness.contracts.diagnosis import (
        CaseDiagnosisRecord,
    )

    record = CaseDiagnosisRecord(
        diagnosis_id="diag_test",
        project_id="proj_1",
        run_id="run_1",
        case_execution_id="exec_1",
        case_id="case_1",
        attempt_number=1,
        requirement_version="v1.0",
        evaluator_version="c1-evaluator-v1.0",
        cause_category=CauseCategory.AGENT_BEHAVIOUR,
        explanation_summary="Deterministic finding: agent called wrong tool.",
        evidence_refs=["ev_legit_1"],
    )

    async def _run_test():
        # Subtest A: Provider fails with exception -> fallback to deterministic
        async def failing_callable(**kwargs):
            raise RuntimeError("Provider service timed out")

        failing_provider = ModelAssistedDiagnosisProvider(
            model_callable=failing_callable, timeout_seconds=1.0, max_retries=0
        )
        result = await failing_provider.present_diagnosis(record)

        assert (
            result.explanation_method == ExplanationMethod.DETERMINISTIC_RULE_DERIVATION
        )
        assert result.explanation_summary == record.explanation_summary
        assert "Provider service timed out" in (result.metrics.error or "")

        # Subtest B: Provider hallucinates evidence ID not in record.evidence_refs -> caught & fallback
        async def hallucinating_callable(**kwargs):
            return {
                "summary": "Hallucinated summary",
                "cited_evidence": ["ev_fake_999"],  # Fake evidence!
            }

        hallucinating_provider = ModelAssistedDiagnosisProvider(
            model_callable=hallucinating_callable,
            timeout_seconds=1.0,
            max_retries=0,
        )
        result2 = await hallucinating_provider.present_diagnosis(record)

        assert (
            result2.explanation_method
            == ExplanationMethod.DETERMINISTIC_RULE_DERIVATION
        )
        assert result2.explanation_summary == record.explanation_summary
        assert "fabricated non-existent evidence" in (result2.metrics.error or "")

    asyncio.run(_run_test())


def test_9_source_inspector_security(temp_repo: Path):
    """9. Verify SourceInspector security guarantees:
    - Path traversal blocked.
    - Sensitive files blocked.
    - Size limits enforced.
    - No code execution.
    """
    inspector = SourceInspector(temp_repo)

    # Path traversal
    with pytest.raises(SourceInspectionError, match="escapes repository root"):
        inspector.inspect_function("../../../windows/system32/cmd.exe", "run")

    # Sensitive file
    with pytest.raises(SourceInspectionError, match="sensitive path"):
        inspector.inspect_function(".env", "secret")

    # File size limit
    big_file = temp_repo / "app" / "huge_file.py"
    big_file.write_bytes(b"# comment\n" * 15000)  # > 100 KB
    with pytest.raises(SourceInspectionError, match="exceeds maximum inspection limit"):
        inspector.inspect_function("app/huge_file.py", "func")
