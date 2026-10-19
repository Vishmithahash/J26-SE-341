"""Workflow mutation generator for C2 evaluator sensitivity testing.

Generates controlled evaluator mutants across the 8 required operators while
preserving legitimate alternatives, allowed repetitions, and idempotent actions.
"""

import copy
import random

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    TransitionDefinition,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExecutionMode,
    GeneratedTestDefinition,
    MutationProvenance,
    MutationType,
    TestCategory,
    TestReadinessStatus,
)


class WorkflowMutator:
    """Produces controlled workflow mutants from valid reference parent cases.

    Synthetic mutants are controlled evaluator test cases to test the test framework,
    alignment engine, and oracle sensitivity—they are NOT observed LLM failures.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_mutations(
        self,
        base_cases: list[GeneratedTestDefinition],
        model: EFSMModelDefinition,
        mutation_budget: int = 8,
        enabled_types: list[MutationType] | None = None,
    ) -> list[GeneratedTestDefinition]:
        """Generate up to mutation_budget mutants covering the 8 mutation operators."""
        valid_parents = [
            c
            for c in base_cases
            if c.category in (TestCategory.VALID, TestCategory.ALTERNATIVE)
            and len(c.private_reference_transitions) > 0
            and len(c.private_reference_transitions[0]) > 1
        ]
        if not valid_parents:
            return []

        # Collect valid reference transition sequences to reject non-discriminating mutants
        valid_transition_sequences: set[tuple[str, ...]] = set()
        for c in base_cases:
            for p in c.private_reference_transitions:
                valid_transition_sequences.add(tuple(p))

        supported_types = enabled_types or list(MutationType)
        mutated_cases: list[GeneratedTestDefinition] = []
        trans_map: dict[str, TransitionDefinition] = {
            t.id: t for t in model.transitions
        }

        for mut_index, m_type in enumerate(supported_types):
            if len(mutated_cases) >= mutation_budget:
                break

            # Pick a parent case cyclically
            parent = valid_parents[mut_index % len(valid_parents)]

            mutant = self._apply_mutation_operator(
                operator=m_type,
                parent=parent,
                model=model,
                trans_map=trans_map,
                valid_sequences=valid_transition_sequences,
                mutant_id_num=len(mutated_cases) + 1,
            )
            if mutant is not None:
                mutated_cases.append(mutant)

        return mutated_cases

    def _apply_mutation_operator(
        self,
        operator: MutationType,
        parent: GeneratedTestDefinition,
        model: EFSMModelDefinition,
        trans_map: dict[str, TransitionDefinition],
        valid_sequences: set[tuple[str, ...]],
        mutant_id_num: int,
    ) -> GeneratedTestDefinition | None:
        """Apply a specific mutation operator to produce a mutated test case."""
        parent_transitions = list(parent.private_reference_transitions[0])
        parent_states = list(parent.private_reference_paths[0])
        parent_inputs = copy.deepcopy(parent.input_parameters)
        parent_assertions = copy.deepcopy(parent.private_reference_assertions)

        test_id = f"TC-{model.model_id}-MUT-{mutant_id_num:03d}"

        if operator == MutationType.SKIPPED_STEP:
            # Skip an intermediate step (not initial or terminal)
            if len(parent_transitions) < 2:
                return None
            target_idx = 1 if len(parent_transitions) > 2 else 0
            skipped_trans_id = parent_transitions[target_idx]
            skipped_trans = trans_map.get(skipped_trans_id)

            mutated_transitions = (
                parent_transitions[:target_idx] + parent_transitions[target_idx + 1 :]
            )
            mutated_states = (
                parent_states[: target_idx + 1] + parent_states[target_idx + 2 :]
            )

            # Check if matching a valid alternative
            if tuple(mutated_transitions) in valid_sequences:
                return None

            provenance = MutationProvenance(
                mutation_type=MutationType.SKIPPED_STEP,
                parent_case_id=parent.test_id,
                target_step_index=target_idx,
                target_transition_id=skipped_trans_id,
                description=f"Skipped required step '{skipped_trans.trigger_event if skipped_trans else skipped_trans_id}'.",
                targeted_rule=(
                    skipped_trans.source_rules[0]
                    if (skipped_trans and skipped_trans.source_rules)
                    else "RULE_ORDERING"
                ),
                changed_details={"skipped_transition_id": skipped_trans_id},
                intended_violation=f"Omission of required workflow step {skipped_trans_id}",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[mutated_states],
                private_reference_transitions=[mutated_transitions],
                private_reference_assertions=parent_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=mutated_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.REORDERED_STEP:
            # Reorder two adjacent dependent steps
            if len(parent_transitions) < 2:
                return None
            idx = 1 if len(parent_transitions) > 2 else 0
            mutated_transitions = list(parent_transitions)
            mutated_transitions[idx], mutated_transitions[idx + 1] = (
                mutated_transitions[idx + 1],
                mutated_transitions[idx],
            )

            if tuple(mutated_transitions) in valid_sequences:
                return None

            t1 = trans_map.get(parent_transitions[idx])
            t2 = trans_map.get(parent_transitions[idx + 1])

            provenance = MutationProvenance(
                mutation_type=MutationType.REORDERED_STEP,
                parent_case_id=parent.test_id,
                target_step_index=idx,
                target_transition_id=parent_transitions[idx],
                description=f"Reordered adjacent steps '{t1.trigger_event if t1 else 'step1'}' and '{t2.trigger_event if t2 else 'step2'}'.",
                targeted_rule="RULE_ORDERING",
                changed_details={
                    "original_pair": [
                        parent_transitions[idx],
                        parent_transitions[idx + 1],
                    ],
                    "reordered_pair": [
                        mutated_transitions[idx],
                        mutated_transitions[idx + 1],
                    ],
                },
                intended_violation="Causal dependency ordering inversion",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[parent_states],
                private_reference_transitions=[mutated_transitions],
                private_reference_assertions=parent_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=mutated_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.REPEATED_STEP:
            # Repeat a non-idempotent action
            target_idx = -2 if len(parent_transitions) >= 2 else 0
            repeat_trans_id = parent_transitions[target_idx]
            mutated_transitions = list(parent_transitions)
            mutated_transitions.insert(target_idx + 1, repeat_trans_id)

            t = trans_map.get(repeat_trans_id)

            provenance = MutationProvenance(
                mutation_type=MutationType.REPEATED_STEP,
                parent_case_id=parent.test_id,
                target_step_index=target_idx,
                target_transition_id=repeat_trans_id,
                description=f"Duplicated non-repeatable action '{t.trigger_event if t else repeat_trans_id}'.",
                targeted_rule="RULE_NON_REPEATABLE_ACTION",
                changed_details={"repeated_transition_id": repeat_trans_id},
                intended_violation="Duplicate execution of non-idempotent workflow action",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[parent_states],
                private_reference_transitions=[mutated_transitions],
                private_reference_assertions=parent_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=mutated_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.ILLEGAL_TRANSITION:
            # Insert a transition that is not allowed from current state
            illegal_id = "T_ILLEGAL_VERIFY_BEFORE_START"
            mutated_transitions = [illegal_id] + parent_transitions

            provenance = MutationProvenance(
                mutation_type=MutationType.ILLEGAL_TRANSITION,
                parent_case_id=parent.test_id,
                target_step_index=0,
                target_transition_id=illegal_id,
                description="Injected invalid tool call from start state.",
                targeted_rule="RULE_STATE_MACHINE_INTEGRITY",
                changed_details={"injected_transition": illegal_id},
                intended_violation="Invocation of action without valid transition edge in reference EFSM",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[parent_states],
                private_reference_transitions=[mutated_transitions],
                private_reference_assertions=parent_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=mutated_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.WRONG_ENTITY:
            # Substitute entity in input parameters (e.g. order_id: 503 -> 501 or 502)
            mutated_inputs = copy.deepcopy(parent_inputs)
            original_val = None
            substituted_val = 502  # Ineligible order ID

            for args in mutated_inputs.values():
                if isinstance(args, dict):
                    for k in ("order_id", "selected_order_id"):
                        if k in args:
                            original_val = args[k]
                            args[k] = substituted_val
                            break

            provenance = MutationProvenance(
                mutation_type=MutationType.WRONG_ENTITY,
                parent_case_id=parent.test_id,
                target_step_index=1,
                target_transition_id=parent_transitions[0],
                description="Substituted entity identifier in tool arguments with ineligible entity ID.",
                targeted_rule="RULE_ENTITY_CONTINUITY",
                changed_details={
                    "original_entity_id": original_val,
                    "substituted_entity_id": substituted_val,
                },
                intended_violation="Entity continuity failure: operated on different entity than bound target",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=mutated_inputs,
                private_reference_paths=[parent_states],
                private_reference_transitions=[parent_transitions],
                private_reference_assertions=parent_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=parent_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.MISSING_EFFECT:
            # Omit expected effect assertion from terminal check
            mutated_assertions = []
            if parent_assertions:
                # Omit first assertion
                mutated_assertions = list(parent_assertions[1:])

            provenance = MutationProvenance(
                mutation_type=MutationType.MISSING_EFFECT,
                parent_case_id=parent.test_id,
                target_step_index=len(parent_transitions) - 1,
                target_transition_id=parent_transitions[-1],
                description="Omitted post-condition state effect assertion from terminal validation.",
                targeted_rule="RULE_EFFECT",
                changed_details={"omitted_assertions_count": 1},
                intended_violation="Post-condition expected effect missing in simulated evaluator state",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[parent_states],
                private_reference_transitions=[parent_transitions],
                private_reference_assertions=mutated_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=parent_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.UNEXPECTED_PROTECTED_STATE_CHANGE:
            # Inject unauthorized protected state change
            mutated_assertions = list(parent_assertions)
            mutated_assertions.append(
                {
                    "check": "protected_field_violation",
                    "field_path": "order_502_payment_status",
                    "expected": "UNPAID",
                    "injected_actual": "MUTATED_UNAUTHORIZED",
                }
            )

            provenance = MutationProvenance(
                mutation_type=MutationType.UNEXPECTED_PROTECTED_STATE_CHANGE,
                parent_case_id=parent.test_id,
                description="Injected unauthorized mutation into protected application state.",
                targeted_rule="RULE_PROTECTED_STATE_INVARIANT",
                changed_details={
                    "field_path": "order_502_payment_status",
                    "injected_value": "MUTATED_UNAUTHORIZED",
                },
                intended_violation="Violation of protected state invariance",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[parent_states],
                private_reference_transitions=[parent_transitions],
                private_reference_assertions=mutated_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=parent_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        elif operator == MutationType.PREMATURE_TERMINATION:
            # Workflow halted before terminal state
            cutoff = max(1, len(parent_transitions) // 2)
            mutated_transitions = parent_transitions[:cutoff]
            mutated_states = parent_states[: cutoff + 1]

            provenance = MutationProvenance(
                mutation_type=MutationType.PREMATURE_TERMINATION,
                parent_case_id=parent.test_id,
                target_step_index=cutoff,
                target_transition_id=parent_transitions[cutoff - 1],
                description=f"Halted workflow prematurely after step {cutoff}.",
                targeted_rule="RULE_MILESTONE_COMPLETION",
                changed_details={
                    "retained_steps": cutoff,
                    "omitted_steps": len(parent_transitions) - cutoff,
                },
                intended_violation="Workflow abandoned prior to reaching declared terminal accepting or rejection state",
            )

            return GeneratedTestDefinition(
                schema_version=parent.schema_version,
                test_id=test_id,
                project_id=parent.project_id,
                suite_id=parent.suite_id,
                pinned_model_id=parent.pinned_model_id,
                pinned_model_version=parent.pinned_model_version,
                model_content_hash=parent.model_content_hash,
                generator_version=parent.generator_version,
                category=TestCategory.MUTATED,
                execution_mode=ExecutionMode.SYNTHETIC_EVALUATOR,
                task=parent.task,
                permitted_context=copy.deepcopy(parent.permitted_context),
                fixture_ref=parent.fixture_ref,
                fixture_version=parent.fixture_version,
                seed=parent.seed,
                input_parameters=parent_inputs,
                private_reference_paths=[mutated_states],
                private_reference_transitions=[mutated_transitions],
                private_reference_assertions=parent_assertions,
                expected_outcome=parent.expected_outcome,
                mutation_provenance=provenance,
                planned_coverage_targets=mutated_transitions,
                readiness=TestReadinessStatus.TEST_READY,
                readiness_reasons=[],
            )

        return None
