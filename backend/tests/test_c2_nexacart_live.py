"""C2 individual live workflow on NexaCart: reference EFSMs, live runner, live-trace mutants, API.

The harness double returns exactly the shape of NexaCart's ``/qa/harness`` responses (as consumed
by LiveNexaCartTargetAdapter). No network access; live runs are covered by
tests/live/test_c2_nexacart_live_e2e.py.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.api.live_router import (
    get_c2_live_target,
    get_c2_session_factory,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
    ViolationType,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    MutationProvenance,
    MutationType,
    TestCategory,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.evaluator.live_mutations import (
    LiveTraceMutator,
)
from app.components.c2_state_aware_workflow.examples.nexacart_workflows import (
    CANCEL_THEN_REFUND_TASK,
    NEXACART_STATE_CHANGING_TOOLS,
    NEXACART_WORKFLOWS,
    OTHER_READ_TOOLS,
    READ_TOOLS,
    build_nexacart_cancel_then_refund_efsm,
    build_nexacart_cancelled_order_refund_efsm,
    build_nexacart_completed_order_cancel_rejection_efsm,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.integration.adapters import (
    ExecutionTrace,
    LiveNexaCartTargetAdapter,
    RawToolEvent,
    StateSnapshot,
    TargetMode,
)
from app.shared.integration.evidence import project_c2_evidence
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

PROJECT_ID = "proj-c2-nexacart-live"
CAPABILITIES = {
    "harnessVersion": "1.0.0",
    "agent": {"provider": "OLLAMA", "model": "qwen3.5:4b"},
    "tools": [
        {"name": name, "isStateChanging": False}
        for name in (*READ_TOOLS, *OTHER_READ_TOOLS)
    ]
    + [
        {"name": name, "isStateChanging": True}
        for name in NEXACART_STATE_CHANGING_TOOLS
    ],
}


def _state(number: str, status: str, payment: str, refunds: int) -> dict[str, Any]:
    return {
        "customer": {"id": 7},
        "orders": {
            "count": 1,
            "latest": {
                "orderNumber": number,
                "status": status,
                "paymentStatus": payment,
                "totalAmount": "50.00",
            },
        },
        "payments": {"count": 1, "latestStatus": payment, "successfulTotal": "50.00"},
        "refunds": {"count": refunds, "successfulTotal": f"{50 * refunds}.00"},
    }


class CancelRefundHarness:
    """NexaCart-shaped harness double for the cancel-then-refund workflow.

    ``behaviour``: conforming | refund_first | stops_after_cancel | provider_error
    """

    base_url = "http://nexacart.test/api/v1"

    def __init__(self, behaviour: str = "conforming"):
        self.behaviour = behaviour
        self.fixtures = 0
        self.instructions: list[str] = []

    def check_readiness(self):
        return True, []

    def get_capabilities(self):
        return CAPABILITIES

    def create_fixture(self, definition):
        self.fixtures += 1
        number = f"NXC-QA-{self.fixtures:03d}"
        return {
            "fixtureId": f"fx-{self.fixtures}",
            "context": {"customerId": 7, "orderNumber": number},
            "snapshot": _state(number, "CONFIRMED", "PAID", 0),
        }

    def release_fixture(self, fixture_id):
        return {"fixtureId": fixture_id, "released": True}

    def run_agent(self, fixture_id, instruction, qa_run_id=None, fault_profile=None):
        self.instructions.append(instruction)
        number = f"NXC-QA-{int(fixture_id.split('-')[1]):03d}"
        calls: list[dict[str, Any]] = []
        snaps: list[dict[str, Any]] = []
        state = {"status": "CONFIRMED", "payment": "PAID", "refunds": 0}

        def call(tool, ok=True, error=None, changes=None):
            seq = len(calls) + 1
            calls.append(
                {
                    "id": f"call-{fixture_id}-{seq}",
                    "sequenceNumber": seq,
                    "toolName": tool,
                    "arguments": {"orderNumber": number}
                    if tool != "list_orders"
                    else {},
                    "status": "SUCCEEDED" if ok else "FAILED",
                    "result": {"ok": True, "data": {"orderNumber": number}}
                    if ok
                    else {"ok": False, "error": {"errorCode": error}},
                    "errorCode": None if ok else error,
                    "durationMs": 5,
                    "createdAt": "2026-10-25T10:00:00Z",
                }
            )
            if tool in NEXACART_STATE_CHANGING_TOOLS:
                state.update(changes or {})
                snaps.append(
                    {
                        "afterSequenceNumber": seq,
                        "snapshot": _state(
                            number, state["status"], state["payment"], state["refunds"]
                        ),
                    }
                )

        if self.behaviour == "provider_error":
            return {
                "fixtureId": fixture_id,
                "qaRunId": f"{qa_run_id}-x",
                "agentRun": {
                    "id": f"run-{fixture_id}",
                    "status": "FAILED",
                    "toolCalls": [],
                },
                "agentError": {
                    "errorCode": "LLM_PROVIDER_ERROR",
                    "message": "Ollama unreachable",
                },
                "beforeSnapshot": _state(number, "CONFIRMED", "PAID", 0),
                "intermediateSnapshots": [],
                "afterSnapshot": _state(number, "CONFIRMED", "PAID", 0),
                "faultReceipts": [],
                "idempotencyKeys": {},
                "observationErrors": [],
            }

        call("list_orders")
        if self.behaviour == "refund_first":
            call("refund_order", ok=False, error="REFUND_ORDER_NOT_CANCELLED")
        call("cancel_order", changes={"status": "CANCELLED"})
        if self.behaviour != "stops_after_cancel":
            call("refund_order", changes={"payment": "REFUNDED", "refunds": 1})
        return {
            "fixtureId": fixture_id,
            "qaRunId": f"{qa_run_id}-x",
            "durationMs": 900,
            "agentRun": {
                "id": f"run-{fixture_id}",
                "status": "COMPLETED",
                "provider": "OLLAMA",
                "model": "qwen3.5:4b",
                "finalAnswer": f"Order {number} was cancelled and refunded.",
                "toolCalls": calls,
            },
            "agentError": None,
            "beforeSnapshot": _state(number, "CONFIRMED", "PAID", 0),
            "intermediateSnapshots": snaps,
            "afterSnapshot": _state(
                number, state["status"], state["payment"], state["refunds"]
            ),
            "faultReceipts": [],
            "idempotencyKeys": {},
            "observationErrors": [],
        }


# -- reference models -----------------------------------------------------------


def test_reference_workflows_validate_and_use_only_real_nexacart_tools():
    real_tools = {*READ_TOOLS, *OTHER_READ_TOOLS, *NEXACART_STATE_CHANGING_TOOLS}
    assert len(NEXACART_WORKFLOWS) == 5
    kinds = {w.kind for w in NEXACART_WORKFLOWS.values()}
    assert kinds == {"ACCEPTING", "REJECTION"}
    for workflow in NEXACART_WORKFLOWS.values():
        model = workflow.builder(PROJECT_ID)
        is_valid, status, *_ = ModelValidationService(db=None).validate_definition(
            model
        )
        assert is_valid and status == "READY", model.model_id
        assert {t.trigger_event for t in model.transitions} <= real_tools
        assert model.protected_fields, model.model_id
        assert workflow.fixture_definition["order"]


# -- live-trace mutations -------------------------------------------------------


def _live_trace(behaviour: str = "conforming") -> ExecutionTrace:
    adapter = LiveNexaCartTargetAdapter(client=CancelRefundHarness(behaviour))
    adapter.prepare_fixture("ns", {"nexacart_fixture": {}})
    return adapter.execute_session("ns", CANCEL_THEN_REFUND_TASK, [], trial_role="C2")


def _test_def(
    model, category=TestCategory.VALID, mutation=None
) -> GeneratedTestDefinition:
    return GeneratedTestDefinition(
        test_id="TC-1",
        project_id=PROJECT_ID,
        pinned_model_id=model.model_id,
        pinned_model_version=model.version,
        model_content_hash="",
        category=category,
        task=CANCEL_THEN_REFUND_TASK,
        fixture_ref="CONFIRMED_PAID_ORDER_FIXTURE",
        expected_outcome=ExpectedOutcomeType.PASS,
        mutation_provenance=mutation,
    )


def _evaluate(model, evidence, fixture, category=TestCategory.VALID):
    return ConformanceEvaluationEngine().evaluate(
        model=model,
        test_def=_test_def(model, category),
        evidence=evidence,
        fixture_data=fixture,
    )


def test_conforming_live_trace_passes_and_ordering_violation_is_localised():
    model = build_nexacart_cancel_then_refund_efsm(PROJECT_ID)
    good = _live_trace("conforming")
    evidence = project_c2_evidence(
        PROJECT_ID, "r1", "TC-1", model.model_id, model.version, good
    )
    result = _evaluate(model, evidence, good.aut_metadata["fixture_context"])
    assert result.verdict == RuntimeVerdict.PASS, result.reasons
    assert result.observed_states == ["START", "ORDER_LOCATED", "CANCELLED", "REFUNDED"]

    bad = _live_trace("refund_first")
    evidence = project_c2_evidence(
        PROJECT_ID, "r2", "TC-1", model.model_id, model.version, bad
    )
    result = _evaluate(model, evidence, bad.aut_metadata["fixture_context"])
    assert result.verdict == RuntimeVerdict.FAIL
    assert result.first_divergence.event_index == 1
    assert result.first_divergence.attempted_event == "refund_order"
    assert "cancel_order" in result.first_divergence.expected_alternatives


@pytest.mark.parametrize("mutation_type", list(MutationType))
def test_every_mutation_of_a_conforming_live_trace_is_detected(mutation_type):
    model = build_nexacart_cancel_then_refund_efsm(PROJECT_ID)
    trace = _live_trace("conforming")
    fixture = trace.aut_metadata["fixture_context"]
    parent = project_c2_evidence(
        PROJECT_ID, "r1", "TC-1", model.model_id, model.version, trace
    )
    provenance = MutationProvenance(
        mutation_type=mutation_type, description="test mutant"
    )
    mutation = LiveTraceMutator(model).mutate(
        parent, provenance, "TC-M", "r1-m", fixture
    )
    assert mutation.applied, mutation.reason
    assert mutation.evidence.execution_mode == "live_trace_mutation"
    assert mutation.evidence.collector_provenance["derived_from_live_execution"] is True
    result = _evaluate(model, mutation.evidence, fixture, TestCategory.MUTATED)
    assert result.verdict == RuntimeVerdict.FAIL, (mutation_type, result.reasons)
    if mutation_type == MutationType.WRONG_ENTITY:
        assert result.first_divergence.violation_type == ViolationType.ENTITY_MISMATCH
    if mutation_type == MutationType.UNEXPECTED_PROTECTED_STATE_CHANGE:
        assert (
            result.violations[0].violation_type == ViolationType.PROTECTED_FIELD_MUTATED
        )


def test_reordering_a_single_state_change_trace_is_not_applicable():
    model = build_nexacart_cancelled_order_refund_efsm(PROJECT_ID)
    trace = _live_trace("conforming")
    parent = project_c2_evidence(
        PROJECT_ID, "r1", "TC-1", model.model_id, model.version, trace
    )
    # Keep only list_orders + refund_order (one state change)
    single = parent.model_copy(
        update={
            "ordered_events": [parent.ordered_events[0], parent.ordered_events[2]],
            "state_observations": [
                parent.state_observations[0],
                parent.state_observations[2],
            ],
        }
    )
    provenance = MutationProvenance(
        mutation_type=MutationType.REORDERED_STEP, description="m"
    )
    mutation = LiveTraceMutator(model).mutate(single, provenance, "TC-M", "r-m", {})
    assert not mutation.applied
    assert "not discriminating" in mutation.reason


def test_protected_fields_resolve_nested_nexacart_snapshot_paths():
    model = build_nexacart_completed_order_cancel_rejection_efsm(PROJECT_ID)
    number = "NXC-QA-001"
    before = _state(number, "COMPLETED", "PAID", 0)
    after = _state(number, "COMPLETED", "PAID", 0)
    after["payments"]["latestStatus"] = (
        "REFUNDED"  # protected, not covered by an invariant
    )
    trace = ExecutionTrace(
        trace_id="t",
        target_mode=TargetMode.LIVE_AUT,
        is_simulation=False,
        tool_events=[
            RawToolEvent(
                event_id="e1",
                call_index=1,
                tool_name="list_orders",
                arguments={},
                output={"ok": True},
            )
        ],
        initial_state=StateSnapshot(snapshot_id="b", state=before),
        final_state=StateSnapshot(snapshot_id="a", state=after),
        aut_metadata={"fixture_context": {"orderNumber": number}},
    )
    evidence = project_c2_evidence(
        PROJECT_ID, "r", "TC-1", model.model_id, model.version, trace
    )
    test_def = _test_def(model, TestCategory.NEGATIVE).model_copy(
        update={"expected_outcome": ExpectedOutcomeType.EXPECTED_REJECTION_PASS}
    )
    result = ConformanceEvaluationEngine().evaluate(
        model=model,
        test_def=test_def,
        evidence=evidence,
        fixture_data={"orderNumber": number},
    )
    assert result.verdict == RuntimeVerdict.FAIL
    assert result.violations[0].violation_type == ViolationType.PROTECTED_FIELD_MUTATED


# -- API: import -> validate -> approve -> generate -> live execution --------------


@pytest.fixture
def live_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    user = User(
        id=3101,
        name="C2 Live Tester",
        email="c2live@example.com",
        canonical_email="c2live@example.com",
        password_hash="testhash",
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.add(
        Project(
            project_id=PROJECT_ID,
            owner_user_id=3101,
            name="C2 NexaCart Live",
            domain="ecommerce",
            environment="TEST",
            backend_base_url="http://nexacart.test/api/v1",
            backend_health_url="http://nexacart.test/api/v1/health",
            configuration_version=1,
            lifecycle=ProjectLifecycle.ACTIVE.value,
            connection_state=ProjectConnectionState.CONNECTED.value,
        )
    )
    db.commit()
    harness = CancelRefundHarness()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: user
    app.dependency_overrides[get_c2_live_target] = lambda: LiveNexaCartTargetAdapter(
        client=harness
    )
    app.dependency_overrides[get_c2_session_factory] = lambda: factory
    with TestClient(app) as client:
        yield client, harness
    app.dependency_overrides.clear()
    db.close()


BASE = f"/api/v1/c2/projects/{PROJECT_ID}"
LIVE = f"{BASE}/live/nexacart"


def _approved_suite(client, model_id="nxc_cancel_then_refund") -> dict:
    imported = client.post(f"{LIVE}/workflows/{model_id}/import")
    assert imported.status_code == 201, imported.text
    version = imported.json()["version"]
    assert imported.json()["lifecycle_status"] == "DRAFT"
    validated = client.post(f"{BASE}/models/{model_id}/versions/{version}/validate")
    assert validated.status_code == 200, validated.text
    approved = client.post(
        f"{BASE}/models/{model_id}/versions/{version}/approve",
        json={"reviewer_id": "tester", "review_basis": "NexaCart services"},
    )
    assert approved.status_code == 200, approved.text
    suite = client.post(
        f"{BASE}/suites/generate",
        json={
            "model_id": model_id,
            "version": version,
            "case_budget": 4,
            "mutation_budget": 8,
        },
    )
    assert suite.status_code in (200, 201), suite.text
    return suite.json()


def _cases(client, suite_id) -> list[dict]:
    res = client.get(f"{BASE}/suites/{suite_id}/cases")
    assert res.status_code == 200, res.text
    body = res.json()
    return body["items"] if isinstance(body, dict) and "items" in body else body


def test_live_api_runs_generated_suite_on_nexacart(live_api):
    client, harness = live_api
    ready = client.get(f"{LIVE}/readiness").json()
    assert ready["ready"] is True and ready["harness_version"] == "1.0.0"

    workflows = client.get(f"{LIVE}/workflows").json()
    assert {w["model_id"] for w in workflows} == set(NEXACART_WORKFLOWS)

    suite = _approved_suite(client)
    cases = _cases(client, suite["suite_id"])
    valid = next(c for c in cases if c["category"] == "valid")
    mutant_cases = [c for c in cases if c["category"] == "mutated"]
    mutants = [c["test_id"] for c in mutant_cases]
    parents = {
        client.get(f"{BASE}/suites/{suite['suite_id']}/cases/{c['test_id']}").json()[
            "definition"
        ]["mutation_provenance"]["parent_case_id"]
        for c in mutant_cases
    }
    assert len(mutants) == 8

    # Selecting only mutants: each parent is executed live first, exactly once.
    start = client.post(
        f"{LIVE}/executions", json={"suite_id": suite["suite_id"], "test_ids": mutants}
    )
    assert start.status_code == 202, start.text
    execution = client.get(f"{LIVE}/executions/{start.json()['execution_id']}").json()
    assert execution["status"] == "COMPLETED", execution
    results = execution["case_results"]
    live = [r for r in results if r["category"] != "mutated"]
    assert {r["test_id"] for r in live} == parents
    assert {r["verdict"] for r in live} == {"PASS"}
    assert live[0]["agent_run_id"] and live[0]["tool_sequence"] == [
        "list_orders",
        "cancel_order",
        "refund_order",
    ]
    # Oracle isolation: NexaCart's agent only ever received the task text.
    assert set(harness.instructions) == {valid["task"]}
    assert len(harness.instructions) == len(parents)
    summary = execution["summary"]
    assert summary["mutation"]["applied"] == 8
    assert summary["mutation"]["detection_score"] == 1.0
    assert summary["live"]["conformance_rate"] == 1.0
    assert summary["coverage"]["workflow_transitions_covered"] >= 3

    evals = client.get(f"{BASE}/evaluations").json()
    items = evals["items"] if isinstance(evals, dict) else evals
    assert len(items) == len(mutants) + len(parents)

    # The report states that NexaCart's LLM agent ran; only shared services are not wired in.
    live_eval = next(e for e in items if e["test_id"] in parents)
    prov = client.get(f"{BASE}/evaluations/{live_eval['evaluation_id']}/report").json()[
        "execution_provenance"
    ]
    assert prov["is_live_execution"] is True
    assert prov["live_capabilities_available"] is True
    assert "live_llm_runner" not in prov["unavailable_live_capabilities"]


def test_live_api_reports_ordering_violation_and_provider_errors(live_api):
    client, harness = live_api
    suite = _approved_suite(client)
    valid = [
        c["test_id"]
        for c in _cases(client, suite["suite_id"])
        if c["category"] == "valid"
    ]

    harness.behaviour = "refund_first"
    start = client.post(
        f"{LIVE}/executions",
        json={"suite_id": suite["suite_id"], "test_ids": valid[:1]},
    )
    execution = client.get(f"{LIVE}/executions/{start.json()['execution_id']}").json()
    result = execution["case_results"][0]
    assert result["verdict"] == "FAIL"
    assert result["first_divergence"]["attempted_event"] == "refund_order"
    assert execution["summary"]["first_divergences"][0]["event_index"] == 1

    harness.behaviour = "provider_error"
    start = client.post(
        f"{LIVE}/executions",
        json={"suite_id": suite["suite_id"], "test_ids": valid[:1]},
    )
    execution = client.get(f"{LIVE}/executions/{start.json()['execution_id']}").json()
    assert execution["status"] == "ERROR"
    assert execution["case_results"][0]["status"] == "ERROR"
    assert execution["case_results"][0]["verdict"] is None


def test_live_execution_requires_a_nexacart_reference_suite(live_api):
    client, _ = live_api
    res = client.post(f"{LIVE}/executions", json={"suite_id": "missing"})
    assert res.status_code == 404
    res = client.post(f"{LIVE}/workflows/unknown_model/import")
    assert res.status_code == 404
