"""Tests for C2 deterministic candidate model builder."""

import pytest

from app.components.c2_state_aware_workflow.builder.deterministic import (
    DeterministicCandidateBuilder,
    InsufficientInputError,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    BusinessRule,
    ObservableStateMapping,
    SyntheticFixtureReference,
    ToolParameterSpec,
    ToolSpecification,
    WorkflowInputContract,
)


def test_builder_rejects_insufficient_inputs():
    builder = DeterministicCandidateBuilder()
    empty_input = WorkflowInputContract(
        project_id="p1",
        domain="ecommerce",
        workflow_id="w1",
        name="Empty",
        task="",  # empty task
        business_rules=[],  # no rules
        tool_specifications=[],  # no tools
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="", description=""
        ),  # empty fixture
    )

    with pytest.raises(InsufficientInputError) as exc_info:
        builder.build_candidate_model(empty_input)

    diagnostics = exc_info.value.diagnostics
    assert any("task description" in d for d in diagnostics)
    assert any("business rules" in d for d in diagnostics)
    assert any("tool specifications" in d for d in diagnostics)
    assert any("fixture reference" in d for d in diagnostics)


def test_builder_constructs_valid_candidate_model():
    builder = DeterministicCandidateBuilder()
    workflow_input = WorkflowInputContract(
        project_id="test_project",
        domain="ecommerce",
        workflow_id="order_cancellation",
        name="Order Cancellation Workflow",
        version="1.0.0",
        task="Cancel my unfulfilled order.",
        business_rules=[
            BusinessRule(
                rule_id="RULE_CANCEL_ELIGIBLE",
                name="Unfulfilled Order Eligibility",
                description="Orders must be in UNFULFILLED status to be cancelled.",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_CANCEL_EFFECT",
                name="Cancellation Effect",
                description="Cancelled order payment status set to CANCELLED.",
                category="effect",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_REJECT_FULFILLED",
                name="Fulfilled Order Rejection",
                description="Cannot cancel fulfilled orders.",
                category="rejection",
                priority=1,
            ),
        ],
        tool_specifications=[
            ToolSpecification(
                tool_name="list_orders",
                description="List customer orders",
                parameters=[ToolParameterSpec(name="customer_id", type="integer")],
                has_side_effects=False,
            ),
            ToolSpecification(
                tool_name="cancel_order",
                description="Cancel order in database",
                parameters=[ToolParameterSpec(name="order_id", type="integer")],
                has_side_effects=True,
            ),
        ],
        observable_state_mappings=[
            ObservableStateMapping(
                entity_type="orders",
                primary_key="id",
                observable_fields=["id", "status"],
            )
        ],
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="fixture_cancel_test",
            description="Synthetic order cancellation fixture",
            initial_entities={"orders": {"1": {"id": 1, "status": "UNFULFILLED"}}},
            protected_state={"customer_status": "ACTIVE"},
        ),
    )

    model = builder.build_candidate_model(workflow_input)

    assert model.project_id == "test_project"
    assert model.model_id == "order_cancellation"
    assert model.version == "1.0.0"
    assert model.initial_state_id == "START"
    assert "COMPLETED" in model.accepting_state_ids
    assert "REJECTED" in model.rejection_state_ids
    assert len(model.states) >= 4
    assert len(model.transitions) >= 3
    assert len(model.entity_continuity_rules) == 1
    assert model.entity_continuity_rules[0].bound_variable == "selected_order_id"
    assert len(model.protected_fields) == 1
    assert model.protected_fields[0].field_path == "customer_status"
    assert model.builder_version == "c2_deterministic_v1"
