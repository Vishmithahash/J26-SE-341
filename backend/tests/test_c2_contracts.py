"""Tests for C2 contracts, schema versioning, and the six runtime verdicts."""

import pytest
from pydantic import ValidationError

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    StateDefinition,
    StateType,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    EvaluationResultContract,
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    SyntheticFixtureReference,
    WorkflowInputContract,
)


def test_six_runtime_verdicts_exact_values():
    expected_verdicts = {
        "PASS",
        "EXPECTED REJECTION PASS",
        "FAIL",
        "INCONCLUSIVE",
        "MODEL NOT READY",
        "TEST NOT READY",
    }
    actual_verdicts = {v.value for v in RuntimeVerdict}
    assert actual_verdicts == expected_verdicts
    assert len(RuntimeVerdict) == 6


def test_evaluation_result_contract_instantiation():
    result = EvaluationResultContract(
        verdict=RuntimeVerdict.PASS,
        reasons=["All transitions, guards, and invariants satisfied."],
        model_id="order_refund_workflow",
        model_version="1.0.0",
        model_content_hash="abc123def456",
        test_id="T-REFUND-001",
        expected_states=["START", "PAID_ORDERS_RETRIEVED", "REFUNDED"],
        observed_states=["START", "PAID_ORDERS_RETRIEVED", "REFUNDED"],
    )
    assert result.verdict == RuntimeVerdict.PASS
    assert result.schema_version == "2026.1"
    assert result.violations == []
    assert result.first_divergence is None


def test_generated_test_definition_readiness():
    test_def = GeneratedTestDefinition(
        test_id="TEST-001",
        project_id="proj_1",
        pinned_model_id="m_1",
        pinned_model_version="1.0.0",
        model_content_hash="hash_1",
        category=TestCategory.VALID,
        task="Refund my latest paid order",
        fixture_ref="fixture_42",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )
    assert test_def.readiness == TestReadinessStatus.TEST_READY
    assert test_def.category == TestCategory.VALID


def test_contracts_forbid_extra_fields():
    with pytest.raises(ValidationError):
        StateDefinition(
            id="S1",
            name="State 1",
            type=StateType.INITIAL,
            non_existent_field="invalid",  # type: ignore[call-arg]
        )


def test_workflow_input_contract_validation():
    contract = WorkflowInputContract(
        project_id="proj_alpha",
        domain="ecommerce",
        workflow_id="wf_01",
        name="Test Workflow",
        task="Perform test action",
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="fix_01",
            description="Test fixture",
        ),
    )
    assert contract.domain == "ecommerce"
    assert contract.business_rules == []
    assert contract.tool_specifications == []
