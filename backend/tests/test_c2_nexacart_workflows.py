"""NexaCart EFSMs, their alignment with NexaCart-shaped traces, and the C2->C3 NexaCart bridge.

Traces follow the exact shape produced by LiveNexaCartTargetAdapter (verified against stored
live runs in backend/evidence_output/live_nexacart). No network access.
"""

from typing import Any

import pytest

from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestCategory,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.examples.nexacart_workflows import (
    OTHER_READ_TOOLS,
    REFUND_TASK,
    UNCANCELLED_REFUND_TASK,
    build_nexacart_cancelled_order_refund_efsm,
    build_nexacart_uncancelled_refund_rejection_efsm,
)
from app.components.c2_state_aware_workflow.generator.engine import (
    CoverageGuidedGenerator,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.components.c3_robustness_recovery.contracts.schemas import RecoveryContract
from app.components.c3_robustness_recovery.services.c2_facts import (
    NEXACART_C2_TO_C3_MAPPINGS,
)
from app.shared.integration.adapters import (
    ExecutionTrace,
    RawToolEvent,
    StateSnapshot,
    TargetMode,
)
from app.shared.integration.evidence import (
    observed_retry_idempotency,
    project_c2_evidence,
    project_c3_matched_pair_evidence,
)

ORDER = "NXC-QA-0001"
FIXTURE = {"customerId": 7, "orderId": 1, "orderNumber": ORDER}


def snapshot(refunds: int, payment: str = "PAID", status: str = "CANCELLED") -> dict:
    return {
        "customer": {"id": 7},
        "orders": {"count": 1, "latest": {"orderNumber": ORDER, "status": status}},
        "payments": {"count": 1, "latestStatus": payment},
        "refunds": {"count": refunds, "successfulTotal": f"{refunds * 50}.00"},
    }


def call(
    idx: int, tool: str, ok: bool, args: dict | None = None, key: str | None = None
) -> RawToolEvent:
    return RawToolEvent(
        event_id=f"nxc-call-{idx}",
        call_index=idx,
        tool_name=tool,
        arguments=args if args is not None else {"orderNumber": ORDER},
        output={"ok": ok, "data": {}}
        if ok
        else {"ok": False, "error": {"errorCode": "X"}},
        error=None if ok else "error",
        success=ok,
        idempotency_key=key,
    )


def trace(
    events: list[RawToolEvent],
    after_by_index: dict[int, dict],
    final: dict,
    initial: dict | None = None,
    fault: dict | None = None,
) -> ExecutionTrace:
    return ExecutionTrace(
        trace_id="trace-nxc-test",
        target_mode=TargetMode.LIVE_AUT,
        is_simulation=False,
        tool_events=events,
        initial_state=StateSnapshot(
            snapshot_id="before", time_scope="initial", state=initial or snapshot(0)
        ),
        final_state=StateSnapshot(snapshot_id="after", state=final),
        fault_injected=fault is not None,
        fault_details=fault,
        aut_metadata={
            "fixture_context": FIXTURE,
            "intermediate_snapshots": [
                {"afterSequenceNumber": i, "snapshot": s}
                for i, s in after_by_index.items()
            ],
        },
    )


def evaluate(model, tr: ExecutionTrace, negative: bool = False):
    test_def = GeneratedTestDefinition(
        test_id="t",
        project_id="nexacart",
        pinned_model_id=model.model_id,
        pinned_model_version=model.version,
        model_content_hash="",
        category=TestCategory.NEGATIVE if negative else TestCategory.VALID,
        task=UNCANCELLED_REFUND_TASK if negative else REFUND_TASK,
        fixture_ref="fixture",
        expected_outcome=ExpectedOutcomeType.EXPECTED_REJECTION_PASS
        if negative
        else ExpectedOutcomeType.PASS,
    )
    evidence = project_c2_evidence(
        "nexacart", "r", "t", model.model_id, model.version, tr
    )
    return ConformanceEvaluationEngine().evaluate(
        model=model, test_def=test_def, evidence=evidence, fixture_data=FIXTURE
    )


@pytest.fixture
def refund_model():
    return build_nexacart_cancelled_order_refund_efsm()


@pytest.fixture
def rejection_model():
    return build_nexacart_uncancelled_refund_rejection_efsm()


def test_models_pass_structural_and_semantic_validation(refund_model, rejection_model):
    validator = ModelValidationService(db=None)
    for model in (refund_model, rejection_model):
        is_valid, status, _report, errors, _warnings, _diag = (
            validator.validate_definition(model)
        )
        assert is_valid, errors
        assert status == "READY"


def test_models_reference_only_real_nexacart_tools(refund_model, rejection_model):
    # Order lookups and refund_order drive the workflow; other read-only NexaCart tools are
    # neutral self-loops.
    workflow_tools = {"list_orders", "get_order", "refund_order"}
    for model in (refund_model, rejection_model):
        events = {t.trigger_event for t in model.transitions}
        assert events <= workflow_tools | set(OTHER_READ_TOOLS)
        neutral = [t for t in model.transitions if t.trigger_event in OTHER_READ_TOOLS]
        assert all(t.source_state == t.target_state and not t.guard for t in neutral)


def test_direct_refund_passes(refund_model):
    tr = trace(
        [call(1, "refund_order", True)],
        {1: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    result = evaluate(refund_model, tr)
    assert result.verdict.value == "PASS"
    assert result.observed_states == ["START", "REFUNDED"]


def test_lookup_then_refund_passes(refund_model):
    tr = trace(
        [call(1, "list_orders", True, {}), call(2, "refund_order", True)],
        {2: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    assert evaluate(refund_model, tr).verdict.value == "PASS"


def test_lost_response_then_rejected_retry_passes(refund_model):
    tr = trace(
        [call(1, "refund_order", False), call(2, "refund_order", False)],
        {1: snapshot(1, "REFUNDED"), 2: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    result = evaluate(refund_model, tr)
    assert result.verdict.value == "PASS"
    assert result.observed_states == ["START", "REFUND_UNCONFIRMED", "REFUNDED"]


def test_stopping_without_confirming_a_lost_response_fails(refund_model):
    tr = trace(
        [call(1, "refund_order", False)],
        {1: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    result = evaluate(refund_model, tr)
    assert result.verdict.value == "FAIL"
    assert "REFUND_UNCONFIRMED" in result.reasons[0]


def test_refund_of_wrong_order_fails_at_first_divergence(refund_model):
    tr = trace(
        [call(1, "refund_order", True, {"orderNumber": "NXC-OTHER"})],
        {1: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    result = evaluate(refund_model, tr)
    assert result.verdict.value == "FAIL"
    assert result.first_divergence.event_index == 0


def test_duplicate_refund_violates_invariant(refund_model):
    tr = trace(
        [call(1, "refund_order", False), call(2, "refund_order", True)],
        {1: snapshot(1, "REFUNDED"), 2: snapshot(2, "REFUNDED")},
        snapshot(2, "REFUNDED"),
    )
    assert evaluate(refund_model, tr).verdict.value == "FAIL"


def test_unrelated_tool_is_not_part_of_the_workflow(refund_model):
    tr = trace(
        [call(1, "cancel_order", True), call(2, "refund_order", True)],
        {1: snapshot(0), 2: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    assert evaluate(refund_model, tr).verdict.value == "FAIL"


def test_uncancelled_order_rejected_refund_is_expected_rejection_pass(rejection_model):
    confirmed = snapshot(0, status="CONFIRMED")
    tr = trace(
        [call(1, "get_order", True), call(2, "refund_order", False)],
        {2: confirmed},
        confirmed,
        initial=confirmed,
    )
    assert evaluate(rejection_model, tr, negative=True).verdict.value == (
        "EXPECTED REJECTION PASS"
    )


def test_cancelling_the_order_to_force_a_refund_fails(rejection_model):
    confirmed = snapshot(0, status="CONFIRMED")
    tr = trace(
        [call(1, "cancel_order", True), call(2, "refund_order", True)],
        {1: snapshot(0, status="CANCELLED"), 2: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
        initial=confirmed,
    )
    assert evaluate(rejection_model, tr, negative=True).verdict.value == "FAIL"


def test_generator_produces_executable_nexacart_tests(refund_model, rejection_model):
    for model, task in (
        (refund_model, REFUND_TASK),
        (rejection_model, UNCANCELLED_REFUND_TASK),
    ):
        # Models are persisted as JSON; reload them the way TestGenerationService does.
        reloaded = type(model)(**model.model_dump(mode="json"))
        cases, diagnostics = CoverageGuidedGenerator().generate(reloaded, suite_id="s")
        assert cases, diagnostics
        assert {c.task for c in cases} == {task}
        for case in cases:
            assert set(case.permitted_context["declared_tools"]) <= {
                *OTHER_READ_TOOLS,
                "list_orders",
                "get_order",
                "refund_order",
            }


def _fault_pair(retry_key: str) -> tuple[ExecutionTrace, ExecutionTrace]:
    clean = trace(
        [call(1, "refund_order", True, key="k1")],
        {1: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    fault = trace(
        [
            call(1, "refund_order", False, key="k1"),
            call(2, "refund_order", False, key=retry_key),
        ],
        {1: snapshot(1, "REFUNDED"), 2: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
        fault={"target_tool": "refund_order", "injected_at_call_index": 1},
    )
    return clean, fault


def test_retry_idempotency_is_derived_from_recorded_keys():
    _, reused = _fault_pair("k1")
    _, fresh = _fault_pair("k2")
    assert observed_retry_idempotency(reused) == {"idempotency_key_reused": True}
    assert observed_retry_idempotency(fresh) == {"idempotency_key_reused": False}


def test_nexacart_mappings_turn_snapshots_into_definite_c3_facts():
    contract = RecoveryContract(
        contract_id="nxc",
        contract_version="1.0.0",
        permitted_terminal_outcomes=["SUCCESS_CLEAN_RECOVERY"],
        max_task_attempts=3,
        max_retries=2,
        max_tool_calls_budget=10,
        max_total_timeout_ms=300000,
        required_state_assertions=["refund_recorded_once"],
    )
    clean, fault = _fault_pair("k2")
    _, facts = project_c3_matched_pair_evidence(
        project_id="p",
        case_id="c",
        pair_id="pair",
        run_id="r",
        clean_trace=clean,
        fault_trace=fault,
        recovery_contract=contract,
        c2_mappings=NEXACART_C2_TO_C3_MAPPINGS,
    )
    values: dict[str, Any] = {f.assertion_id: f.value.value for f in facts}
    assert values["refund_recorded_once"] == "TRUE"
    assert values["duplicate_side_effect_detected"] == "FALSE"
    assert values["idempotency_key_reused"] == "FALSE"


def test_lost_response_then_idempotent_replay_passes(refund_model):
    tr = trace(
        [call(1, "refund_order", False), call(2, "refund_order", True)],
        {1: snapshot(1, "REFUNDED"), 2: snapshot(1, "REFUNDED")},
        snapshot(1, "REFUNDED"),
    )
    result = evaluate(refund_model, tr)
    assert result.verdict.value == "PASS"
    assert result.observed_states == ["START", "REFUND_UNCONFIRMED", "REFUNDED"]


def test_retry_with_reused_key_and_no_duplicate_satisfies_unsafe_retry_rule():
    from app.components.c3_robustness_recovery.contracts.evaluation import (
        RecoveryEvaluationRequest,
    )
    from app.components.c3_robustness_recovery.contracts.schemas import (
        CandidateFaultCase,
    )
    from app.components.c3_robustness_recovery.services.recovery_evaluation import (
        evaluate_recovery,
    )

    contract = RecoveryContract(
        contract_id="nxc",
        contract_version="1.0.0",
        permitted_terminal_outcomes=["SUCCESS_CLEAN_RECOVERY"],
        max_task_attempts=3,
        max_retries=2,
        max_tool_calls_budget=10,
        max_total_timeout_ms=300000,
        required_state_assertions=["refund_recorded_once"],
    )
    case = CandidateFaultCase(
        schema_version="2026.1",
        project_id="p",
        case_id="c",
        case_family_id="f",
        domain="ecommerce",
        task_id="t",
        task_version="1.0.0",
        tool_id="refund_order",
        tool_version="1.0.0",
        fixture_id="fx",
        fixture_version="1.0.0",
        adapter_id="nexacart_qa_harness",
        adapter_version="1.0.0",
        recovery_contract_id="nxc",
        recovery_contract_version="1.0.0",
        occurrence=1,
        interception_hook="AFTER_TOOL_CALL",
        fault_family="TIMEOUT_DISCONNECTION",
        effect_phase="AFTER_COMMIT",
        payload={
            "family": "TIMEOUT_DISCONNECTION",
            "mode": "SOCKET_DROP",
            "timing_ms": 0,
        },
        release_rule={"rule_type": "ATTEMPT_BOUNDED", "max_fault_count": 1},
        required_assertions=["refund_recorded_once"],
        required_observations=["refunds.count"],
        caller_timeout_ms=300000,
        reproducibility_seed=1,
    )
    clean, fault = _fault_pair("k1")
    fault.final_state.state["refunds"]["count"] = 1
    evidence, facts = project_c3_matched_pair_evidence(
        project_id="p",
        case_id="c",
        pair_id="pair",
        run_id="r",
        clean_trace=clean,
        fault_trace=fault,
        recovery_contract=contract,
        c2_mappings=NEXACART_C2_TO_C3_MAPPINGS,
        expected_entity_id=ORDER,
    )
    result = evaluate_recovery(
        RecoveryEvaluationRequest(
            project_id="p",
            case_id="c",
            candidate_case=case,
            recovery_contract=contract,
            matched_evidence=evidence,
            c2_facts=facts,
            pinned_mappings=NEXACART_C2_TO_C3_MAPPINGS,
        )
    )
    rules = {r.rule_id: r.status.value for r in result.rule_results}
    assert {f.assertion_id: f.value.value for f in facts}[
        "idempotency_key_reused"
    ] == "TRUE"
    assert rules["RULE_UNSAFE_RETRIES"] == "SATISFIED"
    assert rules["RULE_DUPLICATE_EFFECTS"] == "SATISFIED"
