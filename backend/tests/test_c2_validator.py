"""Tests for C2 structural and bounded semantic validators."""

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    FinalOutcome,
    ProtectedField,
    StateDefinition,
    StateType,
    TransitionDefinition,
    VariableDeclaration,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    LogicalOperator,
    LogicalPredicate,
    ScopeEnum,
    VariableUpdate,
    VariableUpdateOp,
)
from app.components.c2_state_aware_workflow.validator.semantic import (
    BoundedSemanticValidator,
)
from app.components.c2_state_aware_workflow.validator.structural import (
    StructuralValidator,
)


def create_minimal_valid_model() -> EFSMModelDefinition:
    return EFSMModelDefinition(
        schema_version="2026.1",
        project_id="p1",
        model_id="m1",
        version="1.0.0",
        name="Valid Model",
        states=[
            StateDefinition(id="START", name="Start", type=StateType.INITIAL),
            StateDefinition(id="STEP1", name="Step 1", type=StateType.INTERMEDIATE),
            StateDefinition(id="DONE", name="Done", type=StateType.TERMINAL_ACCEPTING),
        ],
        initial_state_id="START",
        accepting_state_ids=["DONE"],
        variables=[
            VariableDeclaration(name="x", type="integer", domain=[1, 2]),
        ],
        transitions=[
            TransitionDefinition(
                id="T1",
                source_state="START",
                target_state="STEP1",
                trigger_event="e1",
            ),
            TransitionDefinition(
                id="T2",
                source_state="STEP1",
                target_state="DONE",
                trigger_event="e2",
            ),
        ],
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="DONE",
                description="Done",
            )
        ],
    )


def test_structural_validator_passes_on_valid_model():
    model = create_minimal_valid_model()
    validator = StructuralValidator()
    errors, _warnings = validator.validate(model)
    assert errors == []


def test_structural_validator_detects_duplicate_state_ids():
    model_dict = create_minimal_valid_model().model_dump()
    model_dict["states"].append(
        {
            "id": "STEP1",
            "name": "Duplicate Step 1",
            "type": "intermediate",
            "description": None,
            "milestone": None,
        }
    )
    model = EFSMModelDefinition(**model_dict)
    validator = StructuralValidator()
    errors, _ = validator.validate(model)
    assert any(e["check"] == "unique_state_ids" for e in errors)


def test_structural_validator_detects_dangling_transition():
    model_dict = create_minimal_valid_model().model_dump()
    model_dict["transitions"].append(
        {
            "id": "T_DANGLING",
            "source_state": "START",
            "target_state": "NON_EXISTENT_STATE",
            "trigger_event": "e_ghost",
            "guard": None,
            "actions": [],
            "expected_effects": [],
            "source_rules": [],
            "description": None,
        }
    )
    model = EFSMModelDefinition(**model_dict)
    validator = StructuralValidator()
    errors, _ = validator.validate(model)
    assert any(e["check"] == "valid_target_state" for e in errors)


def test_structural_validator_detects_unreachable_state():
    model_dict = create_minimal_valid_model().model_dump()
    model_dict["states"].append(
        {
            "id": "ORPHAN",
            "name": "Orphan State",
            "type": "intermediate",
            "description": None,
            "milestone": None,
        }
    )
    # Add transition from orphan to done so it's not a dead end, but still unreachable from start
    model_dict["transitions"].append(
        {
            "id": "T_ORPHAN",
            "source_state": "ORPHAN",
            "target_state": "DONE",
            "trigger_event": "e_orphan",
            "guard": None,
            "actions": [],
            "expected_effects": [],
            "source_rules": [],
            "description": None,
        }
    )
    model = EFSMModelDefinition(**model_dict)
    validator = StructuralValidator()
    errors, _ = validator.validate(model)
    assert any(e["check"] == "unreachable_states" for e in errors)


def test_structural_validator_detects_nonterminal_dead_end():
    model_dict = create_minimal_valid_model().model_dump()
    model_dict["states"].append(
        {
            "id": "DEAD_END",
            "name": "Dead End State",
            "type": "intermediate",
            "description": None,
            "milestone": None,
        }
    )
    model_dict["transitions"].append(
        {
            "id": "T_TO_DEAD_END",
            "source_state": "START",
            "target_state": "DEAD_END",
            "trigger_event": "e_trap",
            "guard": None,
            "actions": [],
            "expected_effects": [],
            "source_rules": [],
            "description": None,
        }
    )
    model = EFSMModelDefinition(**model_dict)
    validator = StructuralValidator()
    errors, _ = validator.validate(model)
    assert any(e["check"] == "nonterminal_dead_end" for e in errors)


def test_semantic_validator_detects_contradictory_guard():
    model_dict = create_minimal_valid_model().model_dump()
    # Add contradictory guard: status == 'PAID' AND status == 'UNPAID'
    contradictory_guard = LogicalPredicate(
        op=LogicalOperator.AND,
        clauses=[
            ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="params.status"),
                op=ComparisonOperator.EQUALS,
                right="PAID",
            ),
            ComparisonPredicate(
                left=FieldRef(scope=ScopeEnum.EVENT, path="params.status"),
                op=ComparisonOperator.EQUALS,
                right="UNPAID",
            ),
        ],
    )
    model_dict["transitions"][0]["guard"] = contradictory_guard.model_dump()
    model = EFSMModelDefinition(**model_dict)

    sem_validator = BoundedSemanticValidator()
    errors, _, _ = sem_validator.validate(model)
    assert any(e["check"] == "guard_feasibility" for e in errors)


def test_semantic_validator_detects_conflicting_updates():
    model_dict = create_minimal_valid_model().model_dump()
    model_dict["transitions"][0]["actions"] = [
        VariableUpdate(
            target_var="x", op=VariableUpdateOp.SET, literal_value=1
        ).model_dump(),
        VariableUpdate(
            target_var="x", op=VariableUpdateOp.SET, literal_value=2
        ).model_dump(),
    ]
    model = EFSMModelDefinition(**model_dict)

    sem_validator = BoundedSemanticValidator()
    errors, _, _ = sem_validator.validate(model)
    assert any(e["check"] == "conflicting_updates" for e in errors)


def test_semantic_validator_detects_protected_state_rejection_mutation():
    model_dict = create_minimal_valid_model().model_dump()
    model_dict["states"].append(
        {
            "id": "REJECTED",
            "name": "Rejected",
            "type": "terminal_rejection",
            "description": None,
            "milestone": None,
        }
    )
    model_dict["rejection_state_ids"] = ["REJECTED"]
    model_dict["protected_fields"] = [
        ProtectedField(
            entity_type="ecommerce",
            field_path="order_status",
            strict_unchanged_on_rejection=True,
        ).model_dump()
    ]
    # Add transition to rejection that modifies order_status
    model_dict["transitions"].append(
        {
            "id": "T_REJECT",
            "source_state": "START",
            "target_state": "REJECTED",
            "trigger_event": "reject_evt",
            "guard": None,
            "actions": [
                VariableUpdate(
                    target_var="order_status",
                    op=VariableUpdateOp.SET,
                    literal_value="MODIFIED",
                ).model_dump()
            ],
            "expected_effects": [],
            "source_rules": [],
            "description": None,
        }
    )
    model = EFSMModelDefinition(**model_dict)

    sem_validator = BoundedSemanticValidator()
    errors, _, _ = sem_validator.validate(model)
    assert any(e["check"] == "protected_state_rejection" for e in errors)


def test_semantic_validator_preserves_legitimate_alternative_paths():
    model_dict = create_minimal_valid_model().model_dump()
    # Add alternative intermediate state and alternative branch
    model_dict["states"].append(
        {
            "id": "STEP1_ALT",
            "name": "Step 1 Alternative",
            "type": "intermediate",
            "description": None,
            "milestone": None,
        }
    )
    model_dict["transitions"].append(
        {
            "id": "T_ALT_1",
            "source_state": "START",
            "target_state": "STEP1_ALT",
            "trigger_event": "e_alt",
            "guard": None,
            "actions": [],
            "expected_effects": [],
            "source_rules": [],
            "description": "Legitimate alternative branch",
        }
    )
    model_dict["transitions"].append(
        {
            "id": "T_ALT_2",
            "source_state": "STEP1_ALT",
            "target_state": "DONE",
            "trigger_event": "e2",
            "guard": None,
            "actions": [],
            "expected_effects": [],
            "source_rules": [],
            "description": "Alternative path converges to DONE",
        }
    )
    model = EFSMModelDefinition(**model_dict)

    sem_validator = BoundedSemanticValidator()
    errors, _, diag = sem_validator.validate(model)
    assert errors == []
    assert diag["alternative_paths_identified"] >= 1
