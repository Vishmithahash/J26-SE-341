"""Deterministic candidate EFSM model builder for C2.

Constructs formal EFSM models from structured workflow inputs without
hallucinating arbitrary rules or relying on external LLM services.
"""

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    EntityContinuityRule,
    EventMapping,
    FinalOutcome,
    MilestoneDefinition,
    ProtectedField,
    StateDefinition,
    StateType,
    TransitionDefinition,
    VariableDeclaration,
    WorkflowInvariant,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    BusinessRule,
    WorkflowInputContract,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    FieldRef,
    LogicalOperator,
    LogicalPredicate,
    PresenceOperator,
    PresencePredicate,
    ScopeEnum,
    StructuredPredicate,
    VariableUpdate,
    VariableUpdateOp,
)


class BuilderError(Exception):
    """Base exception for model builder errors."""


class InsufficientInputError(BuilderError):
    """Raised when workflow input lacks required specifications or business rules."""

    def __init__(self, message: str, diagnostics: list[str]):
        super().__init__(message)
        self.diagnostics = diagnostics


class DeterministicCandidateBuilder:
    """Builds candidate EFSM models deterministically from normalized workflow inputs."""

    def __init__(self, builder_version: str = "c2_deterministic_v1"):
        self.builder_version = builder_version

    def build_candidate_model(
        self, workflow_input: WorkflowInputContract
    ) -> EFSMModelDefinition:
        diagnostics: list[str] = []

        # Validate input sufficiency
        if not workflow_input.task or not workflow_input.task.strip():
            diagnostics.append("Missing required natural language task description.")

        if not workflow_input.business_rules:
            diagnostics.append(
                "Insufficient business rules: at least one domain business rule must be provided."
            )

        if not workflow_input.tool_specifications:
            diagnostics.append(
                "Insufficient tool specifications: at least one tool must be declared."
            )

        if (
            not workflow_input.synthetic_fixture
            or not workflow_input.synthetic_fixture.fixture_id
        ):
            diagnostics.append(
                "Insufficient fixture reference: a valid synthetic fixture reference is required."
            )

        if diagnostics:
            raise InsufficientInputError(
                f"Cannot build candidate EFSM due to {len(diagnostics)} diagnostic failure(s).",
                diagnostics=diagnostics,
            )

        rules_by_category: dict[str, list[BusinessRule]] = {}
        for r in workflow_input.business_rules:
            rules_by_category.setdefault(r.category, []).append(r)

        states: list[StateDefinition] = []
        transitions: list[TransitionDefinition] = []
        variables: list[VariableDeclaration] = []
        event_mappings: list[EventMapping] = []
        invariants: list[WorkflowInvariant] = []
        milestones: list[MilestoneDefinition] = []
        entity_continuity_rules: list[EntityContinuityRule] = []
        protected_fields: list[ProtectedField] = []
        final_outcomes: list[FinalOutcome] = []
        assumptions: list[str] = list(workflow_input.assumptions)

        # 1. Base initial state
        initial_state_id = "START"
        states.append(
            StateDefinition(
                id=initial_state_id,
                name="Start",
                type=StateType.INITIAL,
                description="Initial state before agent workflow execution begins",
            )
        )

        # 2. Derive domain entities & variables from state mappings
        for mapping in workflow_input.observable_state_mappings:
            var_name = f"selected_{mapping.entity_type.removesuffix('s')}_id"
            variables.append(
                VariableDeclaration(
                    name=var_name,
                    type="integer",
                    domain=None,
                    initial_value=None,
                    description=f"Bound identifier for target {mapping.entity_type}",
                )
            )
            entity_continuity_rules.append(
                EntityContinuityRule(
                    id=f"EC_{mapping.entity_type.upper()}",
                    entity_type=mapping.entity_type,
                    key_field=mapping.primary_key,
                    bound_variable=var_name,
                    description=f"Entity continuity for {mapping.entity_type} across workflow steps",
                )
            )

        # 3. Create Event Mappings for each tool specification
        for tool in workflow_input.tool_specifications:
            param_maps = {p.name: p.name for p in tool.parameters}
            event_mappings.append(
                EventMapping(
                    event_id=f"EVT_{tool.tool_name.upper()}",
                    tool_name=tool.tool_name,
                    parameter_mappings=param_maps,
                    description=tool.description,
                )
            )

        # 4. Construct states and transitions based on tools and rules
        read_tools = [
            t for t in workflow_input.tool_specifications if not t.has_side_effects
        ]
        write_tools = [
            t for t in workflow_input.tool_specifications if t.has_side_effects
        ]

        # Intermediate State 1: Discovery / Retrieval
        if read_tools:
            retrieval_tool = read_tools[0]
            retrieval_state_id = "RETRIEVED"
            states.append(
                StateDefinition(
                    id=retrieval_state_id,
                    name="Data Retrieved",
                    type=StateType.INTERMEDIATE,
                    description=f"Retrieved candidate items using {retrieval_tool.tool_name}",
                    milestone="DATA_RETRIEVED",
                )
            )
            milestones.append(
                MilestoneDefinition(
                    id="M_RETRIEVED",
                    name="Data Retrieved",
                    state_id=retrieval_state_id,
                    required=True,
                )
            )
            transitions.append(
                TransitionDefinition(
                    id="T_START_TO_RETRIEVED",
                    source_state=initial_state_id,
                    target_state=retrieval_state_id,
                    trigger_event=retrieval_tool.tool_name,
                    guard=None,
                    actions=[],
                    source_rules=[
                        r.rule_id
                        for r in workflow_input.business_rules
                        if r.category == "ordering"
                    ],
                    description=f"Execute {retrieval_tool.tool_name} from initial state",
                )
            )
            current_source_state = retrieval_state_id
        else:
            current_source_state = initial_state_id

        # Intermediate State 2: Selection / Identification
        selection_state_id = "IDENTIFIED"
        states.append(
            StateDefinition(
                id=selection_state_id,
                name="Target Identified",
                type=StateType.INTERMEDIATE,
                description="Eligible entity identified and bound to workflow context",
                milestone="TARGET_IDENTIFIED",
            )
        )
        milestones.append(
            MilestoneDefinition(
                id="M_IDENTIFIED",
                name="Target Identified",
                state_id=selection_state_id,
                required=True,
            )
        )

        # Guard for eligibility
        eligibility_rules = rules_by_category.get("eligibility", [])
        eligibility_guard: StructuredPredicate | None = None
        if eligibility_rules:
            clauses: list[StructuredPredicate] = []
            for er in eligibility_rules:
                # E.g. presence or status check
                clauses.append(
                    PresencePredicate(
                        target=FieldRef(scope=ScopeEnum.EVENT, path="result"),
                        op=PresenceOperator.EXISTS,
                    )
                )
            eligibility_guard = LogicalPredicate(
                op=LogicalOperator.AND, clauses=clauses
            )

        # Primary update: bind selected entity if available
        first_var = variables[0].name if variables else "selected_id"
        transitions.append(
            TransitionDefinition(
                id="T_TO_IDENTIFIED",
                source_state=current_source_state,
                target_state=selection_state_id,
                trigger_event="identify_target",
                guard=eligibility_guard,
                actions=[
                    VariableUpdate(
                        target_var=first_var,
                        op=VariableUpdateOp.SET,
                        source_ref=FieldRef(
                            scope=ScopeEnum.EVENT, path="params.entity_id"
                        ),
                    )
                ],
                source_rules=[r.rule_id for r in eligibility_rules],
                description="Select eligible target entity",
            )
        )

        # Terminal Accepting State
        accepting_state_id = "COMPLETED"
        states.append(
            StateDefinition(
                id=accepting_state_id,
                name="Workflow Completed",
                type=StateType.TERMINAL_ACCEPTING,
                description="Workflow successfully executed and post-conditions satisfied",
                milestone="OUTCOME_COMPLETED",
            )
        )
        milestones.append(
            MilestoneDefinition(
                id="M_COMPLETED",
                name="Outcome Completed",
                state_id=accepting_state_id,
                required=True,
            )
        )

        action_tool = (
            write_tools[0] if write_tools else (read_tools[-1] if read_tools else None)
        )
        action_tool_name = (
            action_tool.tool_name if action_tool else "execute_workflow_action"
        )

        effect_rules = rules_by_category.get("effect", [])
        expected_effects: list[StructuredPredicate] = []
        for ef in effect_rules:
            expected_effects.append(
                PresencePredicate(
                    target=FieldRef(scope=ScopeEnum.AFTER, path="status"),
                    op=PresenceOperator.IS_NOT_NULL,
                )
            )

        transitions.append(
            TransitionDefinition(
                id="T_IDENTIFIED_TO_COMPLETED",
                source_state=selection_state_id,
                target_state=accepting_state_id,
                trigger_event=action_tool_name,
                guard=None,
                actions=[],
                expected_effects=expected_effects,
                source_rules=[r.rule_id for r in effect_rules],
                description=f"Execute action {action_tool_name} to complete workflow",
            )
        )

        final_outcomes.append(
            FinalOutcome(
                outcome_id="OUTCOME_SUCCESS",
                type="ACCEPTING",
                terminal_state_id=accepting_state_id,
                description="Successful workflow execution fulfilling user task",
            )
        )

        # Terminal Rejection State & Transition (if rejection rules declared)
        rejection_rules = rules_by_category.get("rejection", [])
        rejection_state_ids: list[str] = []
        if rejection_rules:
            rejection_state_id = "REJECTED"
            rejection_state_ids.append(rejection_state_id)
            states.append(
                StateDefinition(
                    id=rejection_state_id,
                    name="Request Rejected",
                    type=StateType.TERMINAL_REJECTION,
                    description="Request cleanly rejected due to eligibility violation or policy rule",
                )
            )
            transitions.append(
                TransitionDefinition(
                    id="T_REJECTION",
                    source_state=selection_state_id,
                    target_state=rejection_state_id,
                    trigger_event="reject_request",
                    guard=None,
                    actions=[],
                    source_rules=[r.rule_id for r in rejection_rules],
                    description="Reject ineligible request",
                )
            )
            final_outcomes.append(
                FinalOutcome(
                    outcome_id="OUTCOME_REJECTION",
                    type="REJECTION",
                    terminal_state_id=rejection_state_id,
                    description="Clean rejection of ineligible request without state alteration",
                )
            )

        # Invariants from invariant rules
        for inv_rule in rules_by_category.get("invariant", []):
            invariants.append(
                WorkflowInvariant(
                    id=f"INV_{inv_rule.rule_id}",
                    name=inv_rule.name,
                    predicate=PresencePredicate(
                        target=FieldRef(scope=ScopeEnum.AFTER, path="protected"),
                        op=PresenceOperator.NOT_EXISTS,
                    ),
                    description=inv_rule.description,
                    source_rule=inv_rule.rule_id,
                )
            )

        # Protected fields from fixture
        if workflow_input.synthetic_fixture.protected_state:
            for field_name in workflow_input.synthetic_fixture.protected_state:
                protected_fields.append(
                    ProtectedField(
                        entity_type=workflow_input.domain,
                        field_path=field_name,
                        strict_unchanged_on_rejection=True,
                        description=f"Protected state field {field_name} must remain unchanged on rejection",
                    )
                )

        return EFSMModelDefinition(
            schema_version=workflow_input.schema_version,
            project_id=workflow_input.project_id,
            model_id=workflow_input.workflow_id,
            version=workflow_input.version,
            name=workflow_input.name,
            description=f"Deterministically constructed model for task: {workflow_input.task}",
            states=states,
            initial_state_id=initial_state_id,
            accepting_state_ids=[accepting_state_id],
            rejection_state_ids=rejection_state_ids,
            variables=variables,
            transitions=transitions,
            event_mappings=event_mappings,
            invariants=invariants,
            milestones=milestones,
            entity_continuity_rules=entity_continuity_rules,
            protected_fields=protected_fields,
            final_outcomes=final_outcomes,
            builder_version=self.builder_version,
            assumptions=assumptions,
            diagnostics=diagnostics,
        )
