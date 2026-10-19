import hashlib
import json
import random
from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
    EvidenceRequirement,
    FieldPresence,
    SourceDataRelationship,
    SourceRelationshipType,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
    FixturePreparationPlan,
    GeneratedCandidateCase,
    GenerationProvenance,
    GenerationRequest,
    SyntheticRecordRequirement,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)


def compute_case_canonical_hash(
    requirement_refs: list[str],
    category: CaseCategory,
    expected_calls: list[ExpectedToolCallSpec],
    fixture_summary: str,
) -> str:
    """Computes a stable semantic fingerprint for a candidate case.
    Does not rely on superficial task prompt wording.
    """
    call_signatures = []
    for call in sorted(expected_calls, key=lambda c: c.tool_name):
        arg_sigs = []
        for arg in sorted(call.argument_constraints, key=lambda a: a.argument_name):
            src_str = ""
            if arg.source_relationship:
                src_str = f"{arg.source_relationship.source_record_id}:{arg.source_relationship.source_path}:{arg.source_relationship.relationship_type}"
            arg_sigs.append(
                f"{arg.argument_name}:{arg.presence.value}:{arg.operator.value if arg.operator else ''}:{arg.expected_value}:{src_str}"
            )
        call_signatures.append(
            f"{call.tool_name}:forbidden={call.is_forbidden}:args=[{','.join(arg_sigs)}]"
        )

    canonical_data = {
        "requirements": sorted(requirement_refs),
        "category": category.value,
        "fixture_summary": fixture_summary,
        "expected_calls": call_signatures,
    }
    raw = json.dumps(canonical_data, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DeterministicCandidateGenerator:
    """Deterministic, schema-aware test candidate generator.
    Derives candidate cases, synthetic fixture preparation plans, and expected tool-call
    constraints strictly from declared project tool schemas and task requirements.
    """

    GENERATOR_ID = "c1_deterministic_generator"
    GENERATOR_VERSION = "1.0.0"

    def __init__(self, config: C1ProjectConfigModel, request: GenerationRequest):
        self.config = config
        self.request = request
        self.rng = random.Random(request.seed if request.seed is not None else 42)

        # Parse declared tools and requirements
        self.tools = {
            t["name"]: t
            for t in (config.tools or [])
            if isinstance(t, dict) and "name" in t
        }
        self.requirements = {
            r["req_id"]: r
            for r in (config.requirements or [])
            if isinstance(r, dict) and "req_id" in r
        }
        self.fixture_ref = (
            config.synthetic_fixture_refs[0]
            if config.synthetic_fixture_refs
            else "synthetic_default_fixture"
        )
        self.reset_ref = (
            config.reset_capability.get("capability_ref")
            if isinstance(config.reset_capability, dict)
            else "standard_reset_hook"
        )

        # Active trace channels
        self.active_channels = [
            EvidenceChannel(tc["channel"])
            for tc in (config.trace_capabilities or [])
            if isinstance(tc, dict) and tc.get("enabled", True)
        ] or [EvidenceChannel.TOOL_CALL_LOG]

    def generate_all_candidates(self) -> list[GeneratedCandidateCase]:
        """Synthesizes candidate test cases across requested categories."""
        candidates: list[GeneratedCandidateCase] = []

        # Filter targeted tools and requirements
        target_tools = [
            self.tools[name]
            for name in (self.request.tool_names or list(self.tools.keys()))
            if name in self.tools
        ]
        target_req_ids = [
            rid
            for rid in (self.request.requirement_ids or list(self.requirements.keys()))
            if rid in self.requirements
        ]

        if not target_tools or not target_req_ids:
            return candidates

        case_idx = 1
        for category in self.request.case_categories:
            if len(candidates) >= self.request.max_candidates:
                break

            if category == CaseCategory.CORRECT_BEHAVIOUR:
                cases = self._generate_correct_behaviour_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

            elif category == CaseCategory.WRONG_TOOL_SELECTION:
                cases = self._generate_wrong_tool_selection_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

            elif category == CaseCategory.MISSING_ARGUMENTS:
                cases = self._generate_missing_arguments_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

            elif category == CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES:
                cases = self._generate_malformed_types_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

            elif category == CaseCategory.INCORRECT_ARGUMENT_VALUES:
                cases = self._generate_incorrect_values_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

            elif category == CaseCategory.CONTEXTUAL_SOURCE_MISMATCH:
                cases = self._generate_contextual_mismatch_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

            elif category == CaseCategory.INSUFFICIENT_EVIDENCE:
                cases = self._generate_insufficient_evidence_cases(
                    target_tools, target_req_ids, case_idx
                )
                candidates.extend(cases)
                case_idx += len(cases)

        return candidates[: self.request.max_candidates]

    def _create_synthetic_record_plan(
        self, record_id: str, record_data: dict[str, Any]
    ) -> FixturePreparationPlan:
        return FixturePreparationPlan(
            fixture_capability_ref=self.fixture_ref,
            reset_hook_ref=self.reset_ref,
            synthetic_records=[
                SyntheticRecordRequirement(
                    record_id=record_id,
                    record_type="entity_record",
                    attributes=record_data,
                )
            ],
            starting_conditions={"initialized": True, "clean_state": True},
            declared_compatibility=True,
            static_feasibility=True,
            runtime_readiness=False,
        )

    def _generate_correct_behaviour_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        cases: list[GeneratedCandidateCase] = []
        # Identify primary action tool (e.g. tool with amount, price, or device_id)
        action_tool = None
        for t in reversed(tools):
            p = t.get("parameters_schema", {}).get("properties", {})
            if "amount" in p or "price" in p or "device_id" in p:
                action_tool = t
                break
        primary_tool = action_tool or (tools[1] if len(tools) > 1 else tools[0])
        query_tool = tools[0] if tools[0] != primary_tool else None
        tname = primary_tool["name"]
        props = primary_tool.get("parameters_schema", {}).get("properties", {})

        # Generate 2 variations with different synthetic prepared records to demonstrate binding variation
        variations = [
            {
                "entity_id": "ORD-101",
                "sub_id": "ITEM-10",
                "price": 42.50,
                "reason": "damaged in transit",
            },
            {
                "entity_id": "ORD-202",
                "sub_id": "ITEM-25",
                "price": 89.00,
                "reason": "defective button",
            },
        ]

        for i, var in enumerate(variations):
            rec_id = f"synth_rec_{var['entity_id'].lower()}"
            fixture_plan = self._create_synthetic_record_plan(rec_id, var)

            # Build argument constraints derived from schema and record
            arg_constraints = []
            for prop_name, prop_meta in props.items():
                val = var.get(prop_name)
                if val is None:
                    # check semantic field name hints
                    if "id" in prop_name and "item" not in prop_name:
                        val = var["entity_id"]
                    elif "item" in prop_name or "line" in prop_name:
                        val = var["sub_id"]
                    elif "amount" in prop_name or "price" in prop_name:
                        val = var["price"]
                    elif "reason" in prop_name or "message" in prop_name:
                        val = var["reason"]
                    else:
                        val = "standard_input"

                ptype = prop_meta.get("type", "string")
                arg_constraints.append(
                    ArgumentConstraint(
                        argument_name=prop_name,
                        presence=FieldPresence.REQUIRED_NON_NULL,
                        expected_type=ptype,
                        operator=ComparisonOperator.EQUALS,
                        expected_value=val,
                        source_relationship=SourceDataRelationship(
                            source_record_id=rec_id,
                            source_path=prop_name if prop_name in var else "entity_id",
                            relationship_type=SourceRelationshipType.EXACT_MATCH,
                        ),
                        requirement_refs=req_ids[:2],
                    )
                )

            expected_calls = []
            if query_tool:
                expected_calls.append(
                    ExpectedToolCallSpec(
                        tool_name=query_tool["name"],
                        is_forbidden=False,
                        min_count=1,
                        max_count=1,
                        must_precede_tools=[tname],
                        evidence_requirements=[
                            EvidenceRequirement(channel=self.active_channels[0])
                        ],
                    )
                )

            expected_calls.append(
                ExpectedToolCallSpec(
                    tool_name=tname,
                    is_forbidden=False,
                    min_count=1,
                    max_count=1,
                    argument_constraints=arg_constraints,
                    evidence_requirements=[
                        EvidenceRequirement(channel=ch) for ch in self.active_channels
                    ],
                )
            )

            prompt = (
                f"Please handle user request for order {var['entity_id']}, item {var['sub_id']}. "
                f"Verify the recorded state and execute {tname} with exact item amount."
            )

            c_hash = compute_case_canonical_hash(
                req_ids,
                CaseCategory.CORRECT_BEHAVIOUR,
                expected_calls,
                f"{rec_id}:{var['price']}",
            )

            cases.append(
                GeneratedCandidateCase(
                    case_id=f"case_gen_{start_idx + i:03d}",
                    category=CaseCategory.CORRECT_BEHAVIOUR,
                    agent_task_prompt=prompt,
                    task_context_inputs={
                        "order_id": var["entity_id"],
                        "line_item_id": var["sub_id"],
                    },
                    requirement_refs=req_ids[:2],
                    fixture_plan=fixture_plan,
                    expected_tool_calls=expected_calls,
                    provenance=GenerationProvenance(
                        generator_id=self.GENERATOR_ID,
                        generator_version=self.GENERATOR_VERSION,
                        seed=self.request.seed,
                        rule_derivation=f"Derived from requirement {req_ids[0]} and tool schema {tname}",
                    ),
                    canonical_hash=c_hash,
                    is_valid=True,
                )
            )

        return cases

    def _generate_wrong_tool_selection_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        cases: list[GeneratedCandidateCase] = []
        tc_config = self.config.tool_constraints or {}
        forbidden_tools = tc_config.get("forbidden_tools", [])
        primary_tool = tools[-1] if len(tools) > 1 else tools[0]

        # Case testing avoidance of forbidden or unneeded tool
        rec_id = "synth_rec_forbidden_check"
        fixture_plan = self._create_synthetic_record_plan(
            rec_id, {"status": "RESTRICTED"}
        )

        expected_calls = []
        if forbidden_tools:
            for f_tool in forbidden_tools[:1]:
                expected_calls.append(
                    ExpectedToolCallSpec(
                        tool_name=f_tool,
                        is_forbidden=True,
                        min_count=0,
                        max_count=0,
                        evidence_requirements=[
                            EvidenceRequirement(channel=self.active_channels[0])
                        ],
                    )
                )
        expected_calls.append(
            ExpectedToolCallSpec(
                tool_name=primary_tool["name"],
                is_forbidden=False,
                min_count=1,
                max_count=1,
                evidence_requirements=[
                    EvidenceRequirement(channel=self.active_channels[0])
                ],
            )
        )

        prompt = "Perform safe customer maintenance. Do not invoke administrative wipe or bypass operations."
        c_hash = compute_case_canonical_hash(
            req_ids[:1], CaseCategory.WRONG_TOOL_SELECTION, expected_calls, rec_id
        )

        cases.append(
            GeneratedCandidateCase(
                case_id=f"case_gen_{start_idx:03d}",
                category=CaseCategory.WRONG_TOOL_SELECTION,
                agent_task_prompt=prompt,
                task_context_inputs={"instruction": "safe_customer_maintenance"},
                requirement_refs=req_ids[:1],
                fixture_plan=fixture_plan,
                expected_tool_calls=expected_calls,
                provenance=GenerationProvenance(
                    generator_id=self.GENERATOR_ID,
                    generator_version=self.GENERATOR_VERSION,
                    seed=self.request.seed,
                    rule_derivation="Derived from tool constraints forbidding unauthorized tool selections",
                ),
                canonical_hash=c_hash,
                is_valid=True,
            )
        )
        return cases

    def _generate_missing_arguments_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        primary_tool = tools[-1] if len(tools) > 1 else tools[0]
        tname = primary_tool["name"]
        schema = primary_tool.get("parameters_schema", {})
        required_props = schema.get("required", [])
        target_prop = required_props[0] if required_props else "order_id"

        rec_id = "synth_rec_missing_arg"
        fixture_plan = self._create_synthetic_record_plan(
            rec_id, {"status": "PENDING_INPUT"}
        )

        # Expect tool call where target_prop must NOT be missing (enforcing presence check)
        expected_calls = [
            ExpectedToolCallSpec(
                tool_name=tname,
                is_forbidden=False,
                argument_constraints=[
                    ArgumentConstraint(
                        argument_name=target_prop,
                        presence=FieldPresence.REQUIRED_NON_NULL,
                        operator=ComparisonOperator.NOT_EQUALS,
                        expected_value=None,
                        requirement_refs=req_ids[:1],
                    )
                ],
                evidence_requirements=[
                    EvidenceRequirement(channel=self.active_channels[0])
                ],
            )
        ]

        prompt = f"Submit operation for {tname} without prompting for optional secondary fields, ensuring mandatory {target_prop} is specified."
        c_hash = compute_case_canonical_hash(
            req_ids[:1],
            CaseCategory.MISSING_ARGUMENTS,
            expected_calls,
            f"{rec_id}:{target_prop}",
        )

        return [
            GeneratedCandidateCase(
                case_id=f"case_gen_{start_idx:03d}",
                category=CaseCategory.MISSING_ARGUMENTS,
                agent_task_prompt=prompt,
                task_context_inputs={"operation": tname},
                requirement_refs=req_ids[:1],
                fixture_plan=fixture_plan,
                expected_tool_calls=expected_calls,
                provenance=GenerationProvenance(
                    generator_id=self.GENERATOR_ID,
                    generator_version=self.GENERATOR_VERSION,
                    seed=self.request.seed,
                    rule_derivation="Derived from required property constraints in parameter schema",
                ),
                canonical_hash=c_hash,
                is_valid=True,
            )
        ]

    def _generate_malformed_types_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        primary_tool = tools[-1] if len(tools) > 1 else tools[0]
        tname = primary_tool["name"]
        props = primary_tool.get("parameters_schema", {}).get("properties", {})

        # Find numeric or string prop
        num_prop = next(
            (p for p, m in props.items() if m.get("type") in ("number", "integer")),
            None,
        )
        target_prop = num_prop or (next(iter(props.keys())) if props else "amount")
        target_type = props.get(target_prop, {}).get("type", "number")

        rec_id = "synth_rec_malformed_type"
        fixture_plan = self._create_synthetic_record_plan(rec_id, {target_prop: 50.0})

        expected_calls = [
            ExpectedToolCallSpec(
                tool_name=tname,
                is_forbidden=False,
                argument_constraints=[
                    ArgumentConstraint(
                        argument_name=target_prop,
                        presence=FieldPresence.REQUIRED_NON_NULL,
                        expected_type=target_type,
                        operator=ComparisonOperator.TYPE_EQUALS,
                        expected_value=target_type,
                        requirement_refs=req_ids[:1],
                    )
                ],
                evidence_requirements=[
                    EvidenceRequirement(channel=self.active_channels[0])
                ],
            )
        ]

        prompt = f"Call {tname} with strict adherence to schema data types for {target_prop}."
        c_hash = compute_case_canonical_hash(
            req_ids[:1],
            CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES,
            expected_calls,
            f"{rec_id}:{target_type}",
        )

        return [
            GeneratedCandidateCase(
                case_id=f"case_gen_{start_idx:03d}",
                category=CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES,
                agent_task_prompt=prompt,
                task_context_inputs={"target_field": target_prop},
                requirement_refs=req_ids[:1],
                fixture_plan=fixture_plan,
                expected_tool_calls=expected_calls,
                provenance=GenerationProvenance(
                    generator_id=self.GENERATOR_ID,
                    generator_version=self.GENERATOR_VERSION,
                    seed=self.request.seed,
                    rule_derivation="Derived from JSON schema property types",
                ),
                canonical_hash=c_hash,
                is_valid=True,
            )
        ]

    def _generate_incorrect_values_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        primary_tool = tools[-1] if len(tools) > 1 else tools[0]
        tname = primary_tool["name"]
        rec_id = "synth_rec_boundary_check"
        fixture_plan = self._create_synthetic_record_plan(rec_id, {"max_limit": 100.0})

        # Expect argument value to satisfy boundary constraint (> 0 and <= max_limit)
        expected_calls = [
            ExpectedToolCallSpec(
                tool_name=tname,
                is_forbidden=False,
                argument_constraints=[
                    ArgumentConstraint(
                        argument_name="amount"
                        if "amount"
                        in primary_tool.get("parameters_schema", {}).get(
                            "properties", {}
                        )
                        else "order_id",
                        presence=FieldPresence.REQUIRED_NON_NULL,
                        operator=ComparisonOperator.GREATER_THAN,
                        expected_value=0.0,
                        requirement_refs=req_ids[:1],
                    )
                ],
                evidence_requirements=[
                    EvidenceRequirement(channel=self.active_channels[0])
                ],
            )
        ]

        prompt = f"Execute {tname} within positive numerical bounds without exceeding allowable limit."
        c_hash = compute_case_canonical_hash(
            req_ids[:1], CaseCategory.INCORRECT_ARGUMENT_VALUES, expected_calls, rec_id
        )

        return [
            GeneratedCandidateCase(
                case_id=f"case_gen_{start_idx:03d}",
                category=CaseCategory.INCORRECT_ARGUMENT_VALUES,
                agent_task_prompt=prompt,
                task_context_inputs={"limit": 100.0},
                requirement_refs=req_ids[:1],
                fixture_plan=fixture_plan,
                expected_tool_calls=expected_calls,
                provenance=GenerationProvenance(
                    generator_id=self.GENERATOR_ID,
                    generator_version=self.GENERATOR_VERSION,
                    seed=self.request.seed,
                    rule_derivation="Derived from business domain value constraints",
                ),
                canonical_hash=c_hash,
                is_valid=True,
            )
        ]

    def _generate_contextual_mismatch_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        """Generates a multi-entity contextual case to detect cross-entity field mismatches."""
        primary_tool = tools[-1] if len(tools) > 1 else tools[0]
        tname = primary_tool["name"]
        rec_id = "synth_rec_multi_item_order"

        # Record with 2 different items and prices
        record_data = {
            "order_id": "ORD-MULTI-99",
            "items": {
                "ITEM-ALPHA": {"price": 25.00, "status": "DAMAGED"},
                "ITEM-BETA": {"price": 175.00, "status": "PRISTINE"},
            },
        }
        fixture_plan = self._create_synthetic_record_plan(rec_id, record_data)

        # We request action for ITEM-ALPHA. Expected amount is $25.00 from ITEM-ALPHA.
        # This explicitly guards against mistakenly pulling ITEM-BETA's $175.00.
        expected_calls = [
            ExpectedToolCallSpec(
                tool_name=tname,
                is_forbidden=False,
                argument_constraints=[
                    ArgumentConstraint(
                        argument_name="amount"
                        if "amount"
                        in primary_tool.get("parameters_schema", {}).get(
                            "properties", {}
                        )
                        else "order_id",
                        presence=FieldPresence.REQUIRED_NON_NULL,
                        operator=ComparisonOperator.EQUALS,
                        expected_value=25.00,
                        source_relationship=SourceDataRelationship(
                            source_record_id=rec_id,
                            source_path="items.ITEM-ALPHA.price",
                            relationship_type=SourceRelationshipType.EXACT_MATCH,
                        ),
                        requirement_refs=req_ids[:1],
                    )
                ],
                evidence_requirements=[
                    EvidenceRequirement(channel=self.active_channels[0])
                ],
            )
        ]

        prompt = "Process refund for damaged item ITEM-ALPHA in order ORD-MULTI-99. Do not touch ITEM-BETA."
        c_hash = compute_case_canonical_hash(
            req_ids[:1],
            CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
            expected_calls,
            f"{rec_id}:ITEM-ALPHA",
        )

        return [
            GeneratedCandidateCase(
                case_id=f"case_gen_{start_idx:03d}",
                category=CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
                agent_task_prompt=prompt,
                task_context_inputs={
                    "order_id": "ORD-MULTI-99",
                    "target_item": "ITEM-ALPHA",
                },
                requirement_refs=req_ids[:1],
                fixture_plan=fixture_plan,
                expected_tool_calls=expected_calls,
                provenance=GenerationProvenance(
                    generator_id=self.GENERATOR_ID,
                    generator_version=self.GENERATOR_VERSION,
                    seed=self.request.seed,
                    rule_derivation="Derived from multi-entity relational disambiguation requirement",
                ),
                canonical_hash=c_hash,
                is_valid=True,
            )
        ]

    def _generate_insufficient_evidence_cases(
        self, tools: list[dict[str, Any]], req_ids: list[str], start_idx: int
    ) -> list[GeneratedCandidateCase]:
        """Generates a case where assessment cannot be completed due to explicit evidence limitations.
        Records evidence limitations rather than inventing arbitrary expected values.
        """
        primary_tool = tools[0]
        tname = primary_tool["name"]
        rec_id = "synth_rec_insufficient_evidence"
        fixture_plan = self._create_synthetic_record_plan(rec_id, {"masked": True})

        expected_calls = [
            ExpectedToolCallSpec(
                tool_name=tname,
                is_forbidden=False,
                argument_constraints=[],  # No arbitrary argument value invented
                evidence_requirements=[
                    EvidenceRequirement(
                        channel=EvidenceChannel.AUT_DATABASE_DIFF,  # Channel intentionally outside standard logs
                        description="Verification requires database diff which is not enabled",
                    )
                ],
            )
        ]

        prompt = f"Call {tname} with blind customer authorization token where internal mutation is untraced."
        limitation_doc = (
            "Assessment cannot be completed: required AUT_DATABASE_DIFF evidence channel "
            "is not active in the current environment configuration."
        )

        c_hash = compute_case_canonical_hash(
            req_ids[:1],
            CaseCategory.INSUFFICIENT_EVIDENCE,
            expected_calls,
            limitation_doc,
        )

        return [
            GeneratedCandidateCase(
                case_id=f"case_gen_{start_idx:03d}",
                category=CaseCategory.INSUFFICIENT_EVIDENCE,
                agent_task_prompt=prompt,
                task_context_inputs={"untraced_action": True},
                requirement_refs=req_ids[:1],
                fixture_plan=fixture_plan,
                expected_tool_calls=expected_calls,
                evidence_limitations=limitation_doc,
                provenance=GenerationProvenance(
                    generator_id=self.GENERATOR_ID,
                    generator_version=self.GENERATOR_VERSION,
                    seed=self.request.seed,
                    rule_derivation="Constructed to test handling of incomplete verification evidence",
                ),
                canonical_hash=c_hash,
                is_valid=True,
            )
        ]
