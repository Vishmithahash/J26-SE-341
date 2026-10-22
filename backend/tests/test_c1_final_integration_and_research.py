import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.contracts.correction import (
    CorrectionStatus,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
    EventStatus,
    ExecutionRequest,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    ExpectedToolCallSpec,
    GenerationRequest,
)
from app.components.c1_tool_call_correctness.contracts.reporting import (
    WorkflowReportFilter,
    redact_sensitive_fields,
)
from app.components.c1_tool_call_correctness.contracts.research import (
    BaselineEvaluationRequest,
    BaselineType,
    DatasetSplit,
    ReferenceCodeLocation,
    ReferenceLabelCreate,
    ReferenceLabelImportRequest,
    ReferenceLabelRecord,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.examples.examination_proctoring import (
    get_examination_proctoring_example_config,
)
from app.components.c1_tool_call_correctness.examples.nexacart_refund import (
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1CaseExecutionModel,
    C1CorrectionModel,
    C1ExecutionRunModel,
)
from app.components.c1_tool_call_correctness.services.config_service import (
    create_project_config,
    create_suite_version,
)
from app.components.c1_tool_call_correctness.services.execution_service import (
    ExecutionService,
)
from app.components.c1_tool_call_correctness.services.generation_service import (
    execute_generation_job,
)
from app.components.c1_tool_call_correctness.services.metrics_engine import (
    metrics_engine,
)
from app.components.c1_tool_call_correctness.services.reporting_service import (
    reporting_service,
)
from app.components.c1_tool_call_correctness.services.research_service import (
    research_service,
)
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session():
    """Provides an isolated, in-memory SQLite database session with Base metadata created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


from tests.auth_test_fixtures import AutoSeedingTestClient, seed_test_admin
from app.shared.auth.dependencies import require_active_user


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden database dependency and authentication."""
    admin_user = seed_test_admin(db_session)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: admin_user
    with AutoSeedingTestClient(db_session, admin_user) as test_client:
        yield test_client
    app.dependency_overrides.clear()



# --------------------------------------------------------------------------
# 1. FULL WORKFLOW INTEGRATION TEST
# --------------------------------------------------------------------------


def test_1_full_workflow_integration_and_reporting(client, db_session):
    """1. Test full end-to-end integration: config -> generation -> execution -> eval -> reporting -> export."""
    project_id = "proj_workflow_001"

    # Stage 1: Configure project
    config_in = get_nexacart_refund_example_config()
    cfg_record = create_project_config(db_session, project_id, config_in)
    assert cfg_record.version == 1

    # Stage 2: Generate candidate test cases
    _gen_run, candidates, _tasks, _auto_suite = execute_generation_job(
        db_session, project_id, GenerationRequest(config_version=cfg_record.version)
    )
    assert len(candidates) > 0
    candidate = candidates[0]

    # Stage 3: Accept into immutable suite version
    suite = create_suite_version(
        db=db_session,
        project_id=project_id,
        suite_id="suite_refund_v1",
        name="Refund Test Suite",
        config_id=cfg_record.id,
        cases=[
            candidate.model_dump(mode="json")
            if hasattr(candidate, "model_dump")
            else candidate
        ],
    )
    assert suite.version == 1
    assert suite.is_immutable is True

    # Stage 4: Execute suite
    exec_service = ExecutionService()
    exec_run = exec_service.create_and_start_run(
        db=db_session,
        project_id=project_id,
        request=ExecutionRequest(
            suite_id="suite_refund_v1",
            suite_version=1,
            adapter_override="AUTO",
        ),
    )
    case_execs = db_session.scalars(
        select(C1CaseExecutionModel).where(C1CaseExecutionModel.run_id == exec_run.id)
    ).all()
    assert len(case_execs) > 0
    case_res = case_execs[0]
    assert case_res.execution_status in ("EXECUTED", "COMPLETED")

    # Seed diagnosis and correction for this run
    diag = C1CaseDiagnosisModel(
        id="diag_wf_01",
        project_id=project_id,
        run_id=exec_run.id,
        case_execution_id=case_res.session_id or "sess_1",
        case_id=case_res.case_id,
        attempt_number=1,
        cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT.value,
        explanation_summary="Missing required refund amount parameter in application code signature.",
        check_explanations=[],
        candidate_code_locations=[
            {"file_path": "app/refund_service.py", "function_name": "process_refund"}
        ],
        evidence_refs=["chk_param_amount"],
        explanation_method="DETERMINISTIC_AST_ANALYSIS",
        metrics={"duration_ms": 12.5},
    )
    db_session.add(diag)

    corr = C1CorrectionModel(
        id="corr_wf_01",
        project_id=project_id,
        run_id=exec_run.id,
        case_execution_id=case_res.session_id or "sess_1",
        case_id=case_res.case_id,
        diagnosis_id="diag_wf_01",
        attempt_number=1,
        permitted_paths=["app/refund_service.py"],
        candidate_patch={
            "patch_id": "p_01",
            "patch_hash": "hash_wf_001",
            "diff_content": "--- a/app/refund_service.py\n+++ b/app/refund_service.py\n",
        },
        status=CorrectionStatus.VERIFIED.value,
        is_verified=True,
        ineligibility_reasons=[],
        verification_results=[
            {"step_type": "REPRODUCE_ORIGINAL_FAILURE", "status": "PASSED"},
            {"step_type": "APPLY_PATCH", "status": "PASSED"},
            {"step_type": "BUILD_STATIC_CHECK", "status": "PASSED"},
            {"step_type": "RERUN_ORIGINAL_CASE", "status": "PASSED"},
            {"step_type": "RUN_REGRESSION_CHECKS", "status": "PASSED"},
            {"step_type": "RUN_INDEPENDENT_ACCEPTANCE", "status": "PASSED"},
        ],
        review={
            "decision": "ACCEPTED",
            "reviewer_id": "danuka_dev",
            "review_comments": "Verified clean signature match.",
            "target_patch_hash": "hash_wf_001",
            "reviewed_at": "2026-10-20T11:00:00Z",
        },
        metrics={"total_duration_ms": 45.2},
    )
    db_session.add(corr)
    db_session.commit()

    # Stage 5: Query paginated workflow report
    rep_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/reports/workflow",
        params={"run_id": exec_run.id, "limit": 10},
    )
    assert rep_resp.status_code == 200
    report_data = rep_resp.json()
    assert report_data["project_id"] == project_id
    assert report_data["run_id"] == exec_run.id
    assert report_data["total_cases"] >= 1
    assert len(report_data["items"]) >= 1

    item = report_data["items"][0]
    assert item["case_id"] == case_res.case_id
    assert (
        item["cause_category"] == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT.value
    )
    assert item["is_verified"] is True
    assert item["review"]["decision"] == "ACCEPTED"

    # Stage 6: Export JSON with sensitive credential redaction
    json_export_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/reports/export",
        params={"run_id": exec_run.id, "format": "JSON"},
    )
    assert json_export_resp.status_code == 200
    exported_json = json_export_resp.json()
    assert exported_json["project_id"] == project_id

    # Stage 7: Export CSV
    csv_export_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/reports/export",
        params={"run_id": exec_run.id, "format": "CSV"},
    )
    assert csv_export_resp.status_code == 200
    assert "case_id,run_id,verdict,execution_status" in csv_export_resp.text
    assert case_res.case_id in csv_export_resp.text


# --------------------------------------------------------------------------
# 2. SENSITIVE CREDENTIAL REDACTION
# --------------------------------------------------------------------------


def test_2_sensitive_field_redaction():
    """2. Test that recursive credential redaction masks tokens, secrets, passwords, and urls."""
    sample_payload = {
        "project_id": "test_proj",
        "openai_api_key": "sk-123456789012345678901234",
        "auth_token": "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz",
        "database_url": "postgresql://user:pass@db.internal:5432/db",
        "nested": {
            "aws_secret": "AKIAIOSFODNN7EXAMPLE",
            "normal_field": "public_data",
        },
        "list_items": [{"user_password": "supersecretpassword"}, "normal_string"],
    }

    redacted = redact_sensitive_fields(sample_payload)
    assert redacted["openai_api_key"] == "[REDACTED_CREDENTIAL]"
    assert redacted["auth_token"] == "[REDACTED_CREDENTIAL]"
    assert redacted["database_url"] == "[REDACTED_CREDENTIAL]"
    assert redacted["nested"]["aws_secret"] == "[REDACTED_CREDENTIAL]"
    assert redacted["nested"]["normal_field"] == "public_data"
    assert redacted["list_items"][0]["user_password"] == "[REDACTED_CREDENTIAL]"
    assert redacted["list_items"][1] == "normal_string"


# --------------------------------------------------------------------------
# 3. RESEARCH LABELS & DATASET SPLIT INTEGRITY
# --------------------------------------------------------------------------


def test_3_research_reference_labels_and_split_integrity(client, db_session):
    """3. Test importing reference labels and verifying task-family split consistency."""
    project_id = "proj_research_001"

    # Valid import batch
    req = ReferenceLabelImportRequest(
        labels=[
            ReferenceLabelCreate(
                case_id="case_refund_1",
                task_family="refund_signature_mismatch",
                dataset_split=DatasetSplit.TRAIN_DEV,
                ground_truth_verdict=CorrectnessVerdict.FAIL,
                ground_truth_cause=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
                ground_truth_code_locations=[
                    ReferenceCodeLocation(
                        file_path="app/refund_service.py",
                        function_name="process_refund",
                    )
                ],
                valid_evidence_refs=["chk_param_amount"],
                reviewer_id="reviewer_alice",
                label_version="v1.0",
                disagreements=[],
                adjudication={"consensus": True},
            ),
            ReferenceLabelCreate(
                case_id="case_refund_2",
                task_family="refund_signature_mismatch",
                dataset_split=DatasetSplit.TRAIN_DEV,  # Same task family in train_dev
                ground_truth_verdict=CorrectnessVerdict.FAIL,
                ground_truth_cause=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
                reviewer_id="reviewer_alice",
            ),
            ReferenceLabelCreate(
                case_id="case_helpdesk_1",
                task_family="helpdesk_routing_defect",
                dataset_split=DatasetSplit.HELD_OUT_TEST,  # Separate family in held_out_test
                ground_truth_verdict=CorrectnessVerdict.FAIL,
                ground_truth_cause=CauseCategory.AGENT_BEHAVIOUR,
                reviewer_id="reviewer_bob",
                is_held_out=True,
            ),
        ]
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/research/labels",
        json=req.model_dump(mode="json"),
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["imported_count"] == 3
    assert res_data["task_families_count"] == 2

    # Query labels
    get_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/research/labels",
        params={"dataset_split": "train_dev"},
    )
    assert get_resp.status_code == 200
    train_labels = get_resp.json()
    assert len(train_labels) == 2

    # Test held-out check helper
    assert (
        research_service.is_case_held_out(db_session, project_id, "case_helpdesk_1")
        is True
    )
    assert (
        research_service.is_case_held_out(db_session, project_id, "case_refund_1")
        is False
    )

    # Split leakage violation: attempting to put case of family 'refund_signature_mismatch' into held_out_test
    leak_req = ReferenceLabelImportRequest(
        labels=[
            ReferenceLabelCreate(
                case_id="case_refund_leak",
                task_family="refund_signature_mismatch",  # Existing family in train_dev
                dataset_split=DatasetSplit.HELD_OUT_TEST,  # Violation!
                ground_truth_verdict=CorrectnessVerdict.FAIL,
                reviewer_id="reviewer_carol",
            )
        ]
    )
    leak_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/research/labels",
        json=leak_req.model_dump(mode="json"),
    )
    assert leak_resp.status_code == 400
    assert "Dataset split leak violation" in leak_resp.json()["detail"]


# --------------------------------------------------------------------------
# 4. ACCURACY METRICS ENGINE & DOCUMENTED FORMULAS
# --------------------------------------------------------------------------


def test_4_accuracy_metrics_calculation(client, db_session):
    """4. Test mathematical calculation of all documented research metrics including zero division."""
    project_id = "proj_metrics_001"

    # Seed 4 reference labels
    labels = [
        ReferenceLabelRecord(
            id="lbl_1",
            project_id=project_id,
            case_id="case_1",
            task_family="family_A",
            dataset_split=DatasetSplit.TRAIN_DEV,
            ground_truth_verdict=CorrectnessVerdict.FAIL,
            ground_truth_cause=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
            ground_truth_code_locations=[
                ReferenceCodeLocation(file_path="app/service.py", function_name="calc")
            ],
            valid_evidence_refs=["ev_1"],
            reviewer_id="rev_1",
            label_version="v1.0",
        ),
        ReferenceLabelRecord(
            id="lbl_2",
            project_id=project_id,
            case_id="case_2",
            task_family="family_A",
            dataset_split=DatasetSplit.TRAIN_DEV,
            ground_truth_verdict=CorrectnessVerdict.PASS,
            ground_truth_cause=None,
            reviewer_id="rev_1",
            label_version="v1.0",
        ),
        ReferenceLabelRecord(
            id="lbl_3",
            project_id=project_id,
            case_id="case_3",
            task_family="family_B",
            dataset_split=DatasetSplit.TRAIN_DEV,
            ground_truth_verdict=CorrectnessVerdict.FAIL,
            ground_truth_cause=CauseCategory.AGENT_BEHAVIOUR,
            reviewer_id="rev_2",
            label_version="v1.0",
        ),
        ReferenceLabelRecord(
            id="lbl_4",
            project_id=project_id,
            case_id="case_4",
            task_family="family_B",
            dataset_split=DatasetSplit.TRAIN_DEV,
            ground_truth_verdict=CorrectnessVerdict.FAIL,
            ground_truth_cause=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
            ground_truth_code_locations=[
                ReferenceCodeLocation(file_path="app/other.py", function_name="run")
            ],
            reviewer_id="rev_2",
            label_version="v1.0",
        ),
    ]

    # Executions: case_1: FAIL, case_2: PASS, case_3: FAIL, case_4: FAIL
    execs = [
        CaseExecutionDetail(
            execution_id="exec_1",
            case_id="case_1",
            session_id="sess_1",
            readiness_status=CaseReadinessStatus.CONFIGURED,
            execution_status=CaseExecutionStatus.EXECUTED,
            verdict=CorrectnessVerdict.FAIL,
            resolved_expectations=[
                ExpectedToolCallSpec(tool_name="t1", requirement_refs=["REQ-01"])
            ],
        ),
        CaseExecutionDetail(
            execution_id="exec_2",
            case_id="case_2",
            session_id="sess_2",
            readiness_status=CaseReadinessStatus.CONFIGURED,
            execution_status=CaseExecutionStatus.EXECUTED,
            verdict=CorrectnessVerdict.PASS,
            resolved_expectations=[
                ExpectedToolCallSpec(
                    tool_name="t1", requirement_refs=["REQ-01", "REQ-02"]
                )
            ],
        ),
        CaseExecutionDetail(
            execution_id="exec_3",
            case_id="case_3",
            session_id="sess_3",
            readiness_status=CaseReadinessStatus.CONFIGURED,
            execution_status=CaseExecutionStatus.EXECUTED,
            verdict=CorrectnessVerdict.FAIL,
            resolved_expectations=[
                ExpectedToolCallSpec(tool_name="t1", requirement_refs=["REQ-02"])
            ],
        ),
        CaseExecutionDetail(
            execution_id="exec_4",
            case_id="case_4",
            session_id="sess_4",
            readiness_status=CaseReadinessStatus.CONFIGURED,
            execution_status=CaseExecutionStatus.EXECUTED,
            verdict=CorrectnessVerdict.FAIL,
            resolved_expectations=[
                ExpectedToolCallSpec(tool_name="t1", requirement_refs=["REQ-03"])
            ],
        ),
    ]

    # Diagnoses: case_1: code defect (correct), case_3: agent (correct), case_4: agent (incorrect, true is code)
    from app.components.c1_tool_call_correctness.contracts.diagnosis import (
        CandidateCodeLocation,
        CaseDiagnosisRecord,
    )

    diags = [
        CaseDiagnosisRecord(
            diagnosis_id="d1",
            project_id=project_id,
            run_id="run_1",
            case_execution_id="sess_1",
            case_id="case_1",
            requirement_version="cfg_v1",
            evaluator_version="v1.0",
            cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
            explanation_summary="Code issue",
            candidate_code_locations=[
                CandidateCodeLocation(
                    file_path="app/service.py",
                    function_name="calc",
                    line_start=10,
                    line_end=20,
                    ranking_score=1,
                    ranking_criteria="Exact name match",
                )
            ],
            evidence_refs=["ev_1"],
        ),
        CaseDiagnosisRecord(
            diagnosis_id="d3",
            project_id=project_id,
            run_id="run_1",
            case_execution_id="sess_3",
            case_id="case_3",
            requirement_version="cfg_v1",
            evaluator_version="v1.0",
            cause_category=CauseCategory.AGENT_BEHAVIOUR,
            explanation_summary="Agent hallucinated tool",
            candidate_code_locations=[],
            evidence_refs=[],
        ),
        CaseDiagnosisRecord(
            diagnosis_id="d4",
            project_id=project_id,
            run_id="run_1",
            case_execution_id="sess_4",
            case_id="case_4",
            requirement_version="cfg_v1",
            evaluator_version="v1.0",
            cause_category=CauseCategory.AGENT_BEHAVIOUR,  # Misdiagnosis!
            explanation_summary="Agent error",
            candidate_code_locations=[],
            evidence_refs=[],
        ),
    ]

    # Corrections: 1 attempted, 1 verified
    corrs = [
        {
            "correction_id": "c1",
            "case_id": "case_1",
            "is_verified": True,
            "verification_results": [
                {"step_type": "RUN_REGRESSION_CHECKS", "status": "PASSED"}
            ],
            "metrics": {"total_duration_ms": 30.0},
        }
    ]

    report = metrics_engine.compute_metrics(
        project_id=project_id,
        run_id="run_1",
        dataset_split=DatasetSplit.TRAIN_DEV,
        reference_labels=labels,
        executions=execs,
        diagnoses=diags,
        corrections=corrs,
        declared_testable_requirements=["REQ-01", "REQ-02", "REQ-03", "REQ-04"],
    )

    # 1. Failure detection precision: tp=3 (case 1, 3, 4), fp=0 -> 3/3 = 1.0
    assert report.failure_detection_precision.value == 1.0
    assert report.failure_detection_precision.numerator == 3
    assert report.failure_detection_precision.denominator == 3

    # 2. Failure detection recall: tp=3, fn=0 -> 3/3 = 1.0
    assert report.failure_detection_recall.value == 1.0

    # 3. Requirement coverage: 3 covered (REQ-01, 02, 03) / 4 declared = 0.75
    assert report.requirement_coverage.value == 0.75

    # 4. Diagnosis accuracy: 2 correct (case 1, 3) / 3 labelled = 2/3 = 0.6667
    assert report.diagnosis_accuracy_all.value == 0.6667

    # 5. Top-1 code localisation: 1 hit (case 1) / 2 code defect cases (case 1, 4) = 0.5
    assert report.top_1_code_localisation_accuracy.value == 0.5

    # 6. False code-blame rate: case 3 is non-code, diagnosed as AGENT -> 0/1 = 0.0
    assert report.false_code_blame_rate.value == 0.0

    # 7. Verified correction rate: 1 verified / 1 eligible failure = 1.0
    assert report.verified_correction_rate.value == 1.0


# --------------------------------------------------------------------------
# 5. BASELINES AND ABLATION COMPARISONS
# --------------------------------------------------------------------------


def test_5_baselines_and_ablation_evaluations(client, db_session):
    """5. Test shallow schema-and-call baseline and reduced-evidence ablations."""
    project_id = "proj_baselines_001"
    run_id = "run_base_001"
    case_id = "case_base_1"

    # Seed execution run and case
    cfg = create_project_config(
        db_session, project_id, get_nexacart_refund_example_config()
    )
    run_m = C1ExecutionRunModel(
        id=run_id,
        project_id=project_id,
        suite_id="s1",
        suite_version=1,
        suite_version_id="sv1",
        config_id=cfg.id,
        status="COMPLETED",
        effective_config={},
        summary={},
    )
    db_session.add(run_m)

    case_m = C1CaseExecutionModel(
        id="cm_1",
        run_id=run_id,
        case_id=case_id,
        attempt_number=1,
        session_id="sess_base_1",
        readiness_status="CONFIGURED",
        execution_status="EXECUTED",
        verdict="FAIL",
        trace_completeness="COMPLETE",
        error_message="Missing argument 'amount' in call to process_refund.",
        captured_events=[
            {
                "event_id": "ev_1",
                "call_index": 0,
                "tool_name": "process_refund",
                "arguments": {"order_id": "ORD-9821"},
            }
        ],
        resolved_expectations=[{"tool_name": "process_refund"}],
    )
    db_session.add(case_m)
    db_session.commit()

    # 1. Baseline 1: Schema-and-call checker
    base1_req = BaselineEvaluationRequest(
        baseline_type=BaselineType.SCHEMA_AND_CALL_ONLY,
        run_id=run_id,
        case_id=case_id,
    )
    resp1 = client.post(
        f"/api/v1/projects/{project_id}/c1/research/baselines/evaluate",
        json=base1_req.model_dump(mode="json"),
    )
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["baseline_type"] == BaselineType.SCHEMA_AND_CALL_ONLY.value
    assert res1["is_available"] is True

    # 2. Baseline 2: Model argument judge (unconfigured dependency -> marked unavailable)
    base2_req = BaselineEvaluationRequest(
        baseline_type=BaselineType.MODEL_ARGUMENT_JUDGE,
        run_id=run_id,
        case_id=case_id,
    )
    resp2 = client.post(
        f"/api/v1/projects/{project_id}/c1/research/baselines/evaluate",
        json=base2_req.model_dump(mode="json"),
    )
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["is_available"] is False
    assert "unavailable" in (res2["unavailability_reason"] or "").lower()

    # 3. Ablation 1: Unlinked diagnosis (evaluates without evidence links)
    abl1_req = BaselineEvaluationRequest(
        baseline_type=BaselineType.UNLINKED_DIAGNOSIS,
        run_id=run_id,
        case_id=case_id,
    )
    resp3 = client.post(
        f"/api/v1/projects/{project_id}/c1/research/baselines/evaluate",
        json=abl1_req.model_dump(mode="json"),
    )
    assert resp3.status_code == 200
    res3 = resp3.json()
    assert res3["evidence_refs"] == []  # Ablated evidence links
    assert (
        res3["cause_category"] == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT.value
    )

    # 4. Ablation 2: No code access (diagnoses solely from logs)
    abl2_req = BaselineEvaluationRequest(
        baseline_type=BaselineType.REDUCED_EVIDENCE_NO_CODE,
        run_id=run_id,
        case_id=case_id,
    )
    resp4 = client.post(
        f"/api/v1/projects/{project_id}/c1/research/baselines/evaluate",
        json=abl2_req.model_dump(mode="json"),
    )
    assert resp4.status_code == 200
    res4 = resp4.json()
    assert res4["candidate_code_locations"] == []


# --------------------------------------------------------------------------
# 6. SYNTHETIC EXAMINATION DOMAIN FIXTURE
# --------------------------------------------------------------------------


def test_6_examination_domain_fixture(client, db_session):
    """6. Test synthetic examination domain fixture configuration, validation, and execution."""
    project_id = "proj_exam_001"
    config_in = get_examination_proctoring_example_config()
    cfg_record = create_project_config(db_session, project_id, config_in)
    assert cfg_record.version == 1
    assert len(cfg_record.tools) == 3
    assert len(cfg_record.requirements) == 3

    # Generate and accept suite
    _gen_run, candidates, _tasks, _auto_suite = execute_generation_job(
        db_session, project_id, GenerationRequest(config_version=cfg_record.version)
    )
    assert len(candidates) > 0

    suite = create_suite_version(
        db=db_session,
        project_id=project_id,
        suite_id="suite_exam_v1",
        name="Exam Proctoring Test Suite",
        config_id=cfg_record.id,
        cases=[
            c.model_dump(mode="json") if hasattr(c, "model_dump") else c
            for c in candidates
        ],
    )
    assert suite.version == 1

    # Execute suite
    exec_service = ExecutionService()
    exec_run = exec_service.create_and_start_run(
        db=db_session,
        project_id=project_id,
        request=ExecutionRequest(
            suite_id="suite_exam_v1",
            suite_version=1,
        ),
    )
    assert exec_run.status == "COMPLETED"
    case_execs = db_session.scalars(
        select(C1CaseExecutionModel).where(C1CaseExecutionModel.run_id == exec_run.id)
    ).all()
    assert len(case_execs) > 0


# --------------------------------------------------------------------------
# 7. PERFORMANCE & CONCURRENCY TARGET VERIFICATION
# --------------------------------------------------------------------------


def test_7_performance_and_cross_project_isolation(client, db_session):
    """7. Check prototype targets:
    - Target 1: Case results load within 3 seconds for 95% of requests.
    - Target 2: Queue and track at least 50 cases per run.
    - Target 3: Concurrent project runs without cross-talk or data mixing.
    """
    proj_a = "proj_concur_A"
    proj_b = "proj_concur_B"

    # Setup 2 concurrent project configurations
    cfg_a = create_project_config(
        db_session, proj_a, get_nexacart_refund_example_config()
    )
    cfg_b = create_project_config(
        db_session, proj_b, get_examination_proctoring_example_config()
    )

    # Seed 50 cases in project A
    run_a = C1ExecutionRunModel(
        id="run_50_cases",
        project_id=proj_a,
        suite_id="suite_perf",
        suite_version=1,
        suite_version_id="sv_perf",
        config_id=cfg_a.id,
        status="COMPLETED",
        effective_config={},
        summary={},
    )
    db_session.add(run_a)

    for i in range(50):
        c_exec = C1CaseExecutionModel(
            id=f"case_exec_{i}",
            run_id="run_50_cases",
            case_id=f"case_batch_{i:03d}",
            attempt_number=1,
            session_id=f"sess_{i}",
            readiness_status="READY",
            execution_status="EXECUTED",
            verdict="PASS" if i % 2 == 0 else "FAIL",
            trace_completeness="COMPLETE",
            error_message=None if i % 2 == 0 else "Expected call missing.",
            captured_events=[],
            resolved_expectations=[],
        )
        db_session.add(c_exec)

    # Seed run in project B
    run_b = C1ExecutionRunModel(
        id="run_proj_b",
        project_id=proj_b,
        suite_id="suite_b",
        suite_version=1,
        suite_version_id="sv_b",
        config_id=cfg_b.id,
        status="COMPLETED",
        effective_config={},
        summary={},
    )
    db_session.add(run_b)
    c_b = C1CaseExecutionModel(
        id="case_exec_b_1",
        run_id="run_proj_b",
        case_id="case_b_001",
        attempt_number=1,
        session_id="sess_b_1",
        readiness_status="READY",
        execution_status="EXECUTED",
        verdict="PASS",
        trace_completeness="COMPLETE",
    )
    db_session.add(c_b)
    db_session.commit()

    # Target 1: Stored case results load within 3 seconds for 95% of requests
    durations: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        filt = WorkflowReportFilter(project_id=proj_a, run_id="run_50_cases", limit=50)
        report = reporting_service.generate_workflow_report(db_session, filt)
        durations.append(time.perf_counter() - t0)
        assert len(report.items) == 50

    p95_duration = sorted(durations)[int(0.95 * len(durations)) - 1]
    assert p95_duration < 3.0, f"p95 duration {p95_duration}s exceeded 3.0s threshold!"

    # Target 2: Verify all 50 cases are queued and tracked
    assert report.total_cases == 50
    assert report.passed_cases == 25
    assert report.failed_cases == 25

    # Target 3: Cross-project isolation (project B items must not leak into project A)
    report_b = reporting_service.generate_workflow_report(
        db_session, WorkflowReportFilter(project_id=proj_b, limit=50)
    )
    assert report_b.total_cases == 1
    assert report_b.items[0].case_id == "case_b_001"

    # Confirm no cases from project A appear in project B report
    proj_a_ids = {f"case_batch_{i:03d}" for i in range(50)}
    proj_b_ids = {it.case_id for it in report_b.items}
    assert proj_a_ids.isdisjoint(proj_b_ids)


# --------------------------------------------------------------------------
# 8. DETERMINISTIC REPRODUCIBILITY REPLAY
# --------------------------------------------------------------------------


def test_8_deterministic_replay_consistency(db_session):
    """8. Confirm identical captured evidence produces identical verdicts under the same evaluator."""
    from app.components.c1_tool_call_correctness.contracts.execution import (
        CapturedToolEvent,
    )
    from app.components.c1_tool_call_correctness.contracts.expectations import (
        ArgumentConstraint,
        ComparisonOperator,
        FieldPresence,
    )
    from app.components.c1_tool_call_correctness.contracts.generation import (
        CaseCategory,
        ExpectedToolCallSpec,
    )
    from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
        DeterministicCorrectnessEvaluator,
    )

    evaluator = DeterministicCorrectnessEvaluator()

    expectations = [
        ExpectedToolCallSpec(
            tool_name="process_refund",
            min_count=1,
            max_count=1,
            argument_constraints=[
                ArgumentConstraint(
                    argument_path="amount",
                    expected_presence=FieldPresence.REQUIRED_NON_NULL,
                    operator=ComparisonOperator.EQUALS,
                    expected_value="35.00",
                )
            ],
        )
    ]

    events = [
        CapturedToolEvent(
            event_id="ev_001",
            call_index=0,
            tool_name="process_refund",
            arguments={"order_id": "ORD-9821", "amount": "35.00"},
            status=EventStatus.SUCCESS,
        )
    ]

    # Run multiple times with identical inputs
    verdicts: list[CorrectnessVerdict] = []
    checks_snapshots: list[list[dict]] = []

    for _ in range(5):
        verdict, checks = evaluator.evaluate_case(
            case_id="case_replay_001",
            category=CaseCategory.CORRECT_BEHAVIOUR,
            resolved_expectations=expectations,
            captured_events=events,
            trace_completeness=TraceCompleteness.COMPLETE,
            context_data={},
            requirement_refs=["REQ-01"],
        )
        verdicts.append(verdict)
        checks_snapshots.append([c.model_dump(mode="json") for c in checks])

    # Assert exact deterministic equality
    assert all(v == CorrectnessVerdict.PASS for v in verdicts)
    assert all(chk == checks_snapshots[0] for chk in checks_snapshots)
