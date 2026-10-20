"""Learning Management System (LMS) workflow definitions for C2 domain portability demonstration.

Scenario: Course enrollment with prerequisites and capacity verification.
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


def get_course_enrollment_workflow_input() -> WorkflowInputContract:
    """Return normalized workflow input for course enrollment."""
    return WorkflowInputContract(
        schema_version="2026.1",
        project_id="c2_domain_portability_project",
        domain="lms",
        workflow_id="course_enrollment_workflow",
        name="Course Enrollment with Prerequisites Workflow",
        version="1.0.0",
        task="Enroll student #ST-101 into CS-301.",
        business_rules=[
            BusinessRule(
                rule_id="RULE_PREREQUISITE_CHECK",
                name="Prerequisites Required",
                description="Student must satisfy all course prerequisites before enrolling.",
                category="eligibility",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_REJECT_UNMET_PREREQS",
                name="Unmet Prerequisite Rejection",
                description="Enrollment must be rejected if prerequisites are not completed.",
                category="rejection",
                priority=1,
            ),
            BusinessRule(
                rule_id="RULE_ENROLLMENT_EFFECT",
                name="Enrollment State Effect",
                description="Successful enrollment creates student course enrollment record.",
                category="effect",
                priority=1,
            ),
        ],
        tools=[
            ToolSpecification(
                tool_name="check_student_eligibility",
                description="Check student prerequisites and course capacity.",
                parameters=[
                    ToolParameterSpec(
                        name="student_id",
                        param_type="string",
                        required=True,
                        description="Student ID",
                    ),
                    ToolParameterSpec(
                        name="course_id",
                        param_type="string",
                        required=True,
                        description="Course ID",
                    ),
                ],
            ),
            ToolSpecification(
                tool_name="enroll_in_course",
                description="Register student in course.",
                parameters=[
                    ToolParameterSpec(
                        name="student_id",
                        param_type="string",
                        required=True,
                        description="Student ID",
                    ),
                    ToolParameterSpec(
                        name="course_id",
                        param_type="string",
                        required=True,
                        description="Course ID",
                    ),
                ],
            ),
        ],
        state_mappings=[
            ObservableStateMapping(
                table_name="student_records",
                entity_id_field="student_id",
                field_mappings={
                    "prerequisites_satisfied": "prerequisites_satisfied",
                },
            )
        ],
        synthetic_fixtures=[
            SyntheticFixtureReference(
                fixture_id="fixture_lms_standard",
                description="Student ST-101 satisfies CS-301 prereqs; ST-102 missing CS-201.",
                seed=42,
            )
        ],
    )


def get_course_enrollment_workflow_model() -> EFSMModelDefinition:
    """Return EFSM model for course enrollment with prerequisites."""
    return EFSMModelDefinition(
        project_id="c2_domain_portability_project",
        model_id="course_enrollment_workflow",
        version="1.0.0",
        name="Course Enrollment with Prerequisites EFSM",
        description="Enrolls students into academic courses after validating prerequisites.",
        initial_state_id="INIT",
        accepting_state_ids=["ENROLLED"],
        rejection_state_ids=["ENROLLMENT_REJECTED"],
        states=[
            StateDefinition(
                id="INIT",
                name="Initial",
                type=StateType.INITIAL,
                description="Initial state before eligibility check.",
            ),
            StateDefinition(
                id="ELIGIBILITY_CHECKED",
                name="Eligibility Checked",
                type=StateType.INTERMEDIATE,
                description="Student prerequisites and capacity confirmed.",
            ),
            StateDefinition(
                id="ENROLLED",
                name="Enrolled",
                type=StateType.TERMINAL_ACCEPTING,
                description="Student officially enrolled in course.",
            ),
            StateDefinition(
                id="ENROLLMENT_REJECTED",
                name="Enrollment Rejected",
                type=StateType.TERMINAL_REJECTION,
                description="Enrollment rejected due to missing prerequisites.",
            ),
        ],
        variables=[
            VariableDeclaration(
                name="target_student_id",
                type="string",
                initial_value=None,
                description="Target student identifier.",
            ),
            VariableDeclaration(
                name="target_course_id",
                type="string",
                initial_value=None,
                description="Target course identifier.",
            ),
        ],
        transitions=[
            TransitionDefinition(
                id="T_CHECK_ELIGIBILITY",
                source_state="INIT",
                target_state="ELIGIBILITY_CHECKED",
                trigger_event="check_student_eligibility",
                guard=None,
                actions=[
                    VariableUpdate(
                        target_var="target_student_id",
                        op=VariableUpdateOp.SET,
                        source_ref=FieldRef(
                            scope=ScopeEnum.EVENT, path="arguments.student_id"
                        ),
                    ),
                    VariableUpdate(
                        target_var="target_course_id",
                        op=VariableUpdateOp.SET,
                        source_ref=FieldRef(
                            scope=ScopeEnum.EVENT, path="arguments.course_id"
                        ),
                    ),
                ],
                source_rules=["RULE_PREREQUISITE_CHECK"],
                description="Verify prerequisites and student standing.",
            ),
            TransitionDefinition(
                id="T_EXECUTE_ENROLLMENT",
                source_state="ELIGIBILITY_CHECKED",
                target_state="ENROLLED",
                trigger_event="enroll_in_course",
                guard=ComparisonPredicate(
                    left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.student_id"),
                    op=ComparisonOperator.EQUALS,
                    right=FieldRef(scope=ScopeEnum.VARS, path="target_student_id"),
                ),
                actions=[],
                expected_effects=[
                    ComparisonPredicate(
                        left=FieldRef(
                            scope=ScopeEnum.AFTER,
                            path="student_records.enrollment_status",
                        ),
                        op=ComparisonOperator.EQUALS,
                        right="ENROLLED",
                    )
                ],
                source_rules=["RULE_ENROLLMENT_EFFECT"],
                description="Register course enrollment.",
            ),
            TransitionDefinition(
                id="T_REJECT_ENROLLMENT",
                source_state="ELIGIBILITY_CHECKED",
                target_state="ENROLLMENT_REJECTED",
                trigger_event="reject_request",
                guard=None,
                actions=[],
                source_rules=["RULE_REJECT_UNMET_PREREQS"],
                description="Reject enrollment when prerequisites are unmet.",
            ),
        ],
        event_mappings=[
            EventMapping(
                event_id="EVT_CHECK_ELIGIBILITY",
                tool_name="check_student_eligibility",
                parameter_mappings={
                    "student_id": "student_id",
                    "course_id": "course_id",
                },
            ),
            EventMapping(
                event_id="EVT_ENROLL",
                tool_name="enroll_in_course",
                parameter_mappings={
                    "student_id": "student_id",
                    "course_id": "course_id",
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
                id="M_PREREQ_VERIFIED",
                name="Prerequisites Verified",
                state_id="ELIGIBILITY_CHECKED",
            ),
            MilestoneDefinition(
                id="M_FINAL_ENROLLED",
                name="Enrolled",
                state_id="ENROLLED",
            ),
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="OUTCOME_ENROLLED",
                type="ACCEPTING",
                terminal_state_id="ENROLLED",
                description="Student record marked as ENROLLED.",
            ),
            FinalOutcome(
                outcome_id="OUTCOME_ENROLL_REJECTED",
                type="REJECTION",
                terminal_state_id="ENROLLMENT_REJECTED",
                description="Enrollment rejected due to missing prerequisites.",
            ),
        ],
        entity_continuity_rules=[
            EntityContinuityRule(
                id="RULE_CONTINUITY_STUDENT",
                entity_type="student_records",
                key_field="student_id",
                bound_variable="target_student_id",
                description="Enrollment must target verified student.",
            )
        ],
    )
