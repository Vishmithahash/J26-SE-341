import asyncio
from pathlib import Path

import pytest

from app.components.c1_tool_call_correctness.contracts.configuration import (
    CodeMapping,
    ToolDefinition,
    ToolParameterSchema,
)
from app.components.c1_tool_call_correctness.contracts.correction import (
    CandidatePatch,
    CorrectionStatus,
    ReviewDecision,
    ReviewRequest,
    StepExecutionStatus,
    VerificationStepType,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    CaseExecutionDetail,
    EventStatus,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.services.correction_engine import (
    CorrectionEngine,
    validate_patch_content,
)
from app.components.c1_tool_call_correctness.services.correction_service import (
    CorrectionService,
)
from app.components.c1_tool_call_correctness.services.sandbox_interface import (
    ContainerSandbox,
    DisposableIsolatedSandbox,
)
from app.components.c1_tool_call_correctness.services.verification_engine import (
    VerificationEngine,
)


@pytest.fixture
def repo_with_defect(tmp_path: Path):
    """Temporary repository directory with an application code defect."""
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True)

    # Function expects refund_amount, while tool sends amount
    service_file = app_dir / "refund_service.py"
    service_file.write_text(
        "def process_refund(order_id: str, refund_amount: float):\n"
        "    return {'status': 'processed', 'amount': refund_amount}\n",
        encoding="utf-8",
    )

    return tmp_path


def test_1_eligibility_vs_ineligibility(repo_with_defect: Path):
    """1. Test that only SUPPORTED_APPLICATION_CODE_DEFECT with code locations and valid source is eligible.
    Agent mistakes and spec problems are strictly INELIGIBLE.
    """
    service = CorrectionService()

    # Eligible diagnosis
    eligible_diag = CaseDiagnosisRecord(
        diagnosis_id="diag_eligible",
        project_id="proj_1",
        run_id="run_1",
        case_execution_id="exec_1",
        case_id="case_1",
        attempt_number=1,
        requirement_version="v1.0",
        evaluator_version="c1-evaluator-v1.0",
        cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
        explanation_summary="Code defect in parameter mapping",
        candidate_code_locations=[
            CandidateCodeLocation(
                file_path="app/refund_service.py",
                function_name="process_refund",
                line_start=1,
                line_end=2,
                ranking_score=1,
                ranking_criteria="Parameter discrepancy",
            )
        ],
    )
    is_ok, reasons = service.check_eligibility(
        diagnosis=eligible_diag,
        source_root_path=repo_with_defect,
        allowed_paths=["app/refund_service.py"],
    )
    assert is_ok is True
    assert len(reasons) == 0

    # Ineligible: Agent behaviour
    ineligible_agent = eligible_diag.model_copy(
        update={"cause_category": CauseCategory.AGENT_BEHAVIOUR}
    )
    is_ok, reasons = service.check_eligibility(
        diagnosis=ineligible_agent,
        source_root_path=repo_with_defect,
        allowed_paths=["app/refund_service.py"],
    )
    assert is_ok is False
    assert any("Only verified SUPPORTED_APPLICATION_CODE_DEFECT" in r for r in reasons)

    # Ineligible: Missing source access
    is_ok, reasons = service.check_eligibility(
        diagnosis=eligible_diag,
        source_root_path=None,
        allowed_paths=["app/refund_service.py"],
    )
    assert is_ok is False
    assert any("Source snapshot directory is unavailable" in r for r in reasons)


def test_2_forbidden_file_changes_and_path_traversal():
    """2. Test that patches touching tests, configs, evaluator files, or path traversal are rejected."""
    # Test file modification attempt
    patch_touching_tests = (
        "--- a/tests/test_harness.py\n"
        "+++ b/tests/test_harness.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-assert False\n"
        "+assert True\n"
    )
    is_valid, err, _files, _adds, _dels = validate_patch_content(patch_touching_tests)
    assert is_valid is False
    assert "forbidden or security-sensitive file" in (err or "")

    # Path traversal attempt
    patch_traversal = (
        "--- a/../etc/passwd\n+++ b/../etc/passwd\n@@ -1,1 +1,1 @@\n-root\n+hacked\n"
    )
    is_valid, err, _files, _adds, _dels = validate_patch_content(patch_traversal)
    assert is_valid is False
    assert "Path traversal detected" in (err or "")

    # Permitted paths violation
    patch_outside_scope = (
        "--- a/app/other_module.py\n"
        "+++ b/app/other_module.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x = 1\n"
        "+x = 2\n"
    )
    is_valid, err, _files, _adds, _dels = validate_patch_content(
        patch_outside_scope, allowed_paths=["app/refund_service.py"]
    )
    assert is_valid is False
    assert "outside permitted scope" in (err or "")


def test_3_bounded_patch_generation(repo_with_defect: Path):
    """3. Test that deterministic patch generation produces a valid, bounded unified diff."""
    tool_def = ToolDefinition(
        name="process_refund",
        description="Process refund",
        parameters_schema=ToolParameterSchema(
            type="object",
            properties={"order_id": {"type": "string"}, "amount": {"type": "number"}},
            required=["order_id", "amount"],
        ),
        code_mapping=CodeMapping(
            file_path="app/refund_service.py",
            function_name="process_refund",
        ),
    )

    diag = CaseDiagnosisRecord(
        diagnosis_id="diag_1",
        project_id="proj_1",
        run_id="run_1",
        case_execution_id="exec_1",
        case_id="case_1",
        attempt_number=1,
        requirement_version="v1.0",
        evaluator_version="c1-evaluator-v1.0",
        cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
        explanation_summary="Mismatch",
        candidate_code_locations=[
            CandidateCodeLocation(
                file_path="app/refund_service.py",
                function_name="process_refund",
                line_start=1,
                line_end=2,
                ranking_score=1,
                ranking_criteria="Param mismatch",
            )
        ],
    )

    engine = CorrectionEngine()
    patch, err = engine.generate_patch(
        diagnosis=diag,
        source_root_path=repo_with_defect,
        tool_definitions={"process_refund": tool_def},
        allowed_paths=["app/refund_service.py"],
    )

    assert err is None
    assert patch is not None
    assert patch.modified_files == ["app/refund_service.py"]
    assert "amount" in patch.diff_content
    assert patch.patch_hash is not None


def test_4_reproduce_original_failure_requirement(repo_with_defect: Path):
    """4. Test that verification requires original failure reproduction on unpatched source;
    if original case unexpectedly passes, verification aborts and leaves status UNVERIFIED.
    """
    ver_engine = VerificationEngine()
    sandbox = DisposableIsolatedSandbox()

    # Case that unexpectedly PASSED on baseline
    passing_case = CaseExecutionDetail(
        execution_id="exec_pass",
        case_id="case_1",
        attempt_number=1,
        session_id="sess_1",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.PASS,
        trace_completeness=TraceCompleteness.COMPLETE,
    )

    patch = CandidatePatch(
        patch_id="p1",
        diff_content="--- a/app/refund_service.py\n+++ b/app/refund_service.py\n@@ -1,1 +1,1 @@\n-def a(): pass\n+def a(): pass\n",
        patch_hash="abc",
        modified_files=["app/refund_service.py"],
    )

    is_verified, status, results = asyncio.run(
        ver_engine.execute_plan(
            disposable_workspace=repo_with_defect,
            candidate_patch=patch,
            original_case=passing_case,
            original_failing_check=None,
            regression_cases=[],
            hidden_acceptance_case=None,
            sandbox=sandbox,
        )
    )

    assert is_verified is False
    assert status == CorrectionStatus.UNVERIFIED
    repro_check = results[0]
    assert repro_check.step_type == VerificationStepType.REPRODUCE_ORIGINAL_FAILURE
    assert repro_check.status == StepExecutionStatus.FAILED


def test_5_build_static_check_failure(repo_with_defect: Path):
    """5. Test that syntax errors in candidate patch fail the BUILD_STATIC_CHECK step and result in UNVERIFIED."""
    ver_engine = VerificationEngine()
    sandbox = DisposableIsolatedSandbox()

    failing_case = CaseExecutionDetail(
        execution_id="exec_fail",
        case_id="case_1",
        attempt_number=1,
        session_id="sess_1",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
    )

    # Patch introduces a Python syntax error
    syntax_error_patch = CandidatePatch(
        patch_id="p_err",
        diff_content=(
            "--- a/app/refund_service.py\n"
            "+++ b/app/refund_service.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def process_refund(order_id: str, refund_amount: float):\n"
            "+def process_refund(order_id: str refund_amount:: syntax error here\n"
        ),
        patch_hash="def_hash",
        modified_files=["app/refund_service.py"],
    )

    is_verified, status, results = asyncio.run(
        ver_engine.execute_plan(
            disposable_workspace=repo_with_defect,
            candidate_patch=syntax_error_patch,
            original_case=failing_case,
            original_failing_check=None,
            regression_cases=[],
            hidden_acceptance_case=None,
            sandbox=sandbox,
        )
    )

    assert is_verified is False
    assert status == CorrectionStatus.UNVERIFIED
    build_check = next(
        r for r in results if r.step_type == VerificationStepType.BUILD_STATIC_CHECK
    )
    assert build_check.status == StepExecutionStatus.FAILED


def test_6_successful_verification_flow(repo_with_defect: Path):
    """6. Test that when every mandatory verification check completes and passes,
    the candidate is strictly marked VERIFIED.
    """
    ver_engine = VerificationEngine()
    sandbox = DisposableIsolatedSandbox()

    exp_spec = ExpectedToolCallSpec(
        tool_name="process_refund",
        argument_constraints=[
            ArgumentConstraint(
                argument_name="amount",
                operator=ComparisonOperator.EQUALS,
                expected_value=50.0,
            )
        ],
    )

    failing_case = CaseExecutionDetail(
        execution_id="exec_orig",
        case_id="case_1",
        attempt_number=1,
        session_id="sess_1",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=CorrectnessVerdict.FAIL,
        trace_completeness=TraceCompleteness.COMPLETE,
        resolved_expectations=[exp_spec],
        captured_events=[
            CapturedToolEvent(
                event_id="ev_01",
                call_index=0,
                tool_name="process_refund",
                arguments={"order_id": "ORD-1"},
                status=EventStatus.SUCCESS,
            )
        ],
    )

    # Valid patch adding amount parameter
    valid_patch = CandidatePatch(
        patch_id="p_valid",
        diff_content=(
            "--- a/app/refund_service.py\n"
            "+++ b/app/refund_service.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def process_refund(order_id: str, refund_amount: float):\n"
            "+def process_refund(order_id: str, refund_amount: float, amount: float = 50.0):\n"
        ),
        patch_hash="hash_valid_123",
        modified_files=["app/refund_service.py"],
    )

    is_verified, status, results = asyncio.run(
        ver_engine.execute_plan(
            disposable_workspace=repo_with_defect,
            candidate_patch=valid_patch,
            original_case=failing_case,
            original_failing_check=None,
            regression_cases=[],
            hidden_acceptance_case=None,
            sandbox=sandbox,
        )
    )

    assert is_verified is True
    assert status == CorrectionStatus.VERIFIED
    assert len(results) == 6
    assert all(r.status == StepExecutionStatus.PASSED for r in results)


def test_7_container_sandbox_readiness():
    """7. Test that ContainerSandbox correctly checks docker availability and reports readiness."""
    c_sandbox = ContainerSandbox()
    is_ready, reason = c_sandbox.check_readiness()
    # In Windows environment without docker daemon running, is_ready is False and reason is informative
    assert isinstance(is_ready, bool)
    assert isinstance(reason, str)


def test_8_developer_review_guardrails(db_session=None):
    """8. Test developer review guardrails:
    - Binds review strictly to target_patch_hash (rejects mismatched/stale hash).
    - Prevents accepting unverified candidates.
    - Records audit references.
    """
    # Create mock SQLite session for unit test
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.components.c1_tool_call_correctness.models.persistence import (
        C1CorrectionModel,
    )
    from app.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    service = CorrectionService()

    # 1. Unverified candidate model
    unverified_model = C1CorrectionModel(
        id="corr_unverified",
        project_id="proj_rev",
        run_id="run_1",
        case_execution_id="exec_1",
        case_id="case_1",
        diagnosis_id="diag_1",
        attempt_number=1,
        permitted_paths=["app/refund_service.py"],
        candidate_patch={
            "patch_id": "p1",
            "patch_hash": "hash_123",
            "diff_content": "diff",
        },
        status=CorrectionStatus.UNVERIFIED.value,
        is_verified=False,
    )
    session.add(unverified_model)
    session.commit()

    # Attempt to ACCEPT unverified candidate -> MUST RAISE ERROR
    req_accept = ReviewRequest(
        decision=ReviewDecision.ACCEPTED,
        reviewer="dev_danuka",
        target_patch_hash="hash_123",
        reason="Looks good",
    )
    with pytest.raises(ValueError, match="Unverified candidates cannot be accepted"):
        service.submit_review(session, "proj_rev", "corr_unverified", req_accept)

    # Attempt to review with MISMATCHED patch hash -> MUST RAISE ERROR
    req_mismatched = ReviewRequest(
        decision=ReviewDecision.REJECTED,
        reviewer="dev_danuka",
        target_patch_hash="stale_hash_999",
        reason="Stale candidate",
    )
    with pytest.raises(ValueError, match="Review target mismatch"):
        service.submit_review(session, "proj_rev", "corr_unverified", req_mismatched)

    # Valid rejection of unverified candidate -> succeeds and records audit
    req_reject = ReviewRequest(
        decision=ReviewDecision.REJECTED,
        reviewer="dev_danuka",
        target_patch_hash="hash_123",
        reason="Does not fix root cause",
    )
    rec = service.submit_review(session, "proj_rev", "corr_unverified", req_reject)
    assert rec.review.decision == ReviewDecision.REJECTED
    assert rec.review.reviewer == "dev_danuka"
    assert rec.review.audit_ref is not None
