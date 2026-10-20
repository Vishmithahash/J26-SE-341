"""Flight booking workflow definitions for C2 domain portability demonstration.

Scenario: Flight cancellation and travel voucher issuance.
"""

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    EntityContinuityRule,
    EventMapping,
    FinalOutcome,
    MilestoneDefinition,
    StateDefinition,
    StateType,
    TransitionDefinition,
    VariableDeclaration,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    BusinessRule,
    ObservableStateMapping,
    SyntheticFixtureReference,
    ToolParameterSpec,
    ToolSpecification,
    WorkflowInputContract,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    ScopeEnum,
    VariableUpdate,
    VariableUpdateOp,
)


def get_flight_cancellation_workflow_input() -> WorkflowInputContract:
    """Return normalized workflow input for flight booking cancellation."""
    return WorkflowInputContract(
        schema_version="2026.1",
        project_id="c2_domain_portability_project",
        domain="flight_booking",
        workflow_id="flight_cancellation_workflow",
        name="Flight Booking Cancellation Workflow",
        version="1.0.0",
        task="Cancel booking #FL-902 and issue travel credit.",
        business_rules=[
            BusinessRule(
                rule_id="RULE_FLIGHT_CUTOFF",
                name="2-Hour Departure Cutoff",
                description="Flights can only be cancelled up to 2 hours before scheduled departure.",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_REJECT_LATE_OR_CHECKED_IN",
                name="Late Cancellation Rejection",
                description="Cancellations under 2 hours or after check-in must be rejected.",
                category="rejection",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_VOUCHER_EFFECT",
                name="Credit Issuance Effect",
                description="Cancelled booking updates booking status to CANCELLED and issues travel voucher.",
                category="effect",
                priority=1,
            ),
        ],
        tools=[
            ToolSpecification(
                tool_name="get_booking_details",
                description="Retrieve booking status and departure time.",
                parameters=[
                    ToolParameterSpec(
                        name="booking_id",
                        param_type="string",
                        required=True,
                        description="Booking reference",
                    )
                ],
            ),
            ToolSpecification(
                tool_name="cancel_flight_booking",
                description="Cancel flight and issue credit.",
                parameters=[
                    ToolParameterSpec(
                        name="booking_id",
                        param_type="string",
                        required=True,
                        description="Booking reference",
                    ),
                    ToolParameterSpec(
                        name="passenger_id",
                        param_type="string",
                        required=True,
                        description="Passenger identifier",
                    ),
                ],
            ),
        ],
        state_mappings=[
            ObservableStateMapping(
                table_name="flight_bookings",
                entity_id_field="booking_id",
                field_mappings={
                    "status": "status",
                    "hours_to_departure": "hours_to_departure",
                },
            )
        ],
        synthetic_fixtures=[
            SyntheticFixtureReference(
                fixture_id="fixture_flight_standard",
                description="Booking FL-902 6 hours to departure; FL-903 1 hour to departure.",
                seed=42,
            )
        ],
    )


def get_flight_cancellation_workflow_model() -> EFSMModelDefinition:
    """Return EFSM model for flight booking cancellation."""
    return EFSMModelDefinition(
        project_id="c2_domain_portability_project",
        model_id="flight_cancellation_workflow",
        version="1.0.0",
        name="Flight Booking Cancellation EFSM",
        description="Cancels flights eligible under the 2-hour departure cutoff.",
        initial_state_id="INIT",
        accepting_state_ids=["FLIGHT_CANCELLED"],
        rejection_state_ids=["FLIGHT_CANCEL_REJECTED"],
        states=[
            StateDefinition(
                id="INIT",
                name="Initial",
                type=StateType.INITIAL,
                description="Initial state before booking inspection.",
            ),
            StateDefinition(
                id="BOOKING_INSPECTED",
                name="Booking Inspected",
                type=StateType.INTERMEDIATE,
                description="Booking status and departure cutoff evaluated.",
            ),
            StateDefinition(
                id="FLIGHT_CANCELLED",
                name="Flight Cancelled",
                type=StateType.TERMINAL_ACCEPTING,
                description="Booking cancelled and travel credit issued.",
            ),
            StateDefinition(
                id="FLIGHT_CANCEL_REJECTED",
                name="Cancellation Rejected",
                type=StateType.TERMINAL_REJECTION,
                description="Cancellation rejected due to departure cutoff violation.",
            ),
        ],
        variables=[
            VariableDeclaration(
                name="selected_booking_id",
                type="string",
                initial_value=None,
                description="Target booking reference.",
            ),
        ],
        transitions=[
            TransitionDefinition(
                id="T_INSPECT_BOOKING",
                source_state="INIT",
                target_state="BOOKING_INSPECTED",
                trigger_event="get_booking_details",
                guard=None,
                actions=[
                    VariableUpdate(
                        target_var="selected_booking_id",
                        op=VariableUpdateOp.SET,
                        source_ref=FieldRef(
                            scope=ScopeEnum.EVENT, path="arguments.booking_id"
                        ),
                    )
                ],
                source_rules=["RULE_FLIGHT_CUTOFF"],
                description="Retrieve booking departure time.",
            ),
            TransitionDefinition(
                id="T_EXECUTE_FLIGHT_CANCEL",
                source_state="BOOKING_INSPECTED",
                target_state="FLIGHT_CANCELLED",
                trigger_event="cancel_flight_booking",
                guard=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.booking_id"),
                    op=ComparisonOperator.EQUALS,
                    right=FieldRef(scope=ScopeEnum.VARS, path="selected_booking_id"),
                ),
                actions=[],
                expected_effects=[
                    ComparisonPredicate(
                        left=FieldRef(
                            scope=ScopeEnum.AFTER, path="flight_bookings.status"
                        ),
                        op=ComparisonOperator.EQUALS,
                        right="CANCELLED",
                    )
                ],
                source_rules=["RULE_VOUCHER_EFFECT"],
                description="Cancel flight and issue travel credit.",
            ),
            TransitionDefinition(
                id="T_REJECT_FLIGHT_CANCEL",
                source_state="BOOKING_INSPECTED",
                target_state="FLIGHT_CANCEL_REJECTED",
                trigger_event="reject_request",
                guard=None,
                actions=[],
                source_rules=["RULE_REJECT_LATE_OR_CHECKED_IN"],
                description="Reject late cancellation.",
            ),
        ],
        event_mappings=[
            EventMapping(
                event_id="EVT_BOOKING_DETAILS",
                tool_name="get_booking_details",
                parameter_mappings={"booking_id": "booking_id"},
            ),
            EventMapping(
                event_id="EVT_CANCEL_FLIGHT",
                tool_name="cancel_flight_booking",
                parameter_mappings={
                    "booking_id": "booking_id",
                    "passenger_id": "passenger_id",
                },
            ),
            EventMapping(
                event_id="EVT_REJECT_REQ",
                tool_name="reject_request",
                parameter_mappings={"reason": "reason"},
            ),
        ],
        milestones=[
            MilestoneDefinition(
                id="M_CUTOFF_CHECKED",
                name="Departure Verified",
                state_id="BOOKING_INSPECTED",
            ),
            MilestoneDefinition(
                id="M_FINAL_FLIGHT_CANCELLED",
                name="Flight Cancelled",
                state_id="FLIGHT_CANCELLED",
            ),
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_FLIGHT_CANCELLED",
                type="ACCEPTING",
                terminal_state_id="FLIGHT_CANCELLED",
                description="Flight booking status is CANCELLED.",
            ),
            FinalOutcome(
                outcome_id="OUTCOME_FLIGHT_REJECTED",
                type="REJECTION",
                terminal_state_id="FLIGHT_CANCEL_REJECTED",
                description="Flight cancellation rejected.",
            ),
        ],
        entity_continuity_rules=[
            EntityContinuityRule(
                id="RULE_CONTINUITY_BOOKING",
                entity_type="flight_bookings",
                key_field="booking_id",
                bound_variable="selected_booking_id",
                description="Flight cancellation must target inspected booking.",
            )
        ],
    )
