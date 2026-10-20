from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
    EvidenceRequirement,
    FieldPresence,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
    GenerationRequest,
)
from app.components.c1_tool_call_correctness.examples.it_helpdesk import (
    get_it_helpdesk_example_config,
)
from app.components.c1_tool_call_correctness.examples.nexacart_refund import (
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)
from app.components.c1_tool_call_correctness.services.candidate_validator import (
    validate_candidate_case,
)
from app.components.c1_tool_call_correctness.services.generator_engine import (
    DeterministicCandidateGenerator,
)
from app.components.c1_tool_call_correctness.services.suite_selector import (
    SuiteSelector,
    extract_agent_facing_task,
)


def _build_dummy_config_model(config_create) -> C1ProjectConfigModel:
    return C1ProjectConfigModel(
        id="cfg_test_uuid",
        project_id="proj_gen_test",
        version=config_create.version,
        is_immutable=False,
        agent_connection_ref=config_create.agent_connection_ref,
        tools=[t.model_dump() for t in config_create.tools],
        requirements=[r.model_dump() for r in config_create.requirements],
        tool_constraints=config_create.tool_constraints.model_dump(),
        expectations=config_create.expectations,
        synthetic_fixture_refs=config_create.synthetic_fixture_refs,
        reset_capability=config_create.reset_capability.model_dump()
        if config_create.reset_capability
        else None,
        trace_capabilities=[tc.model_dump() for tc in config_create.trace_capabilities],
    )


def test_generation_from_two_distinct_input_configurations():
    """Verify that the generator derives cases from two distinct input configurations
    (NexaCart Refund vs IT Helpdesk) adhering to each domain's tools and schemas.
    """
    # 1. NexaCart Refund Configuration
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    nexa_req = GenerationRequest(
        config_version=1, max_candidates=10, max_accepted_cases=5
    )
    nexa_gen = DeterministicCandidateGenerator(nexa_model, nexa_req)
    nexa_candidates = nexa_gen.generate_all_candidates()

    assert len(nexa_candidates) >= 5
    nexa_tools = {
        c.expected_tool_calls[-1].tool_name
        for c in nexa_candidates
        if c.expected_tool_calls
    }
    assert "process_refund" in nexa_tools or "get_order_details" in nexa_tools

    # 2. IT Helpdesk Configuration
    it_spec = get_it_helpdesk_example_config()
    it_model = _build_dummy_config_model(it_spec)
    it_req = GenerationRequest(
        config_version=1, max_candidates=10, max_accepted_cases=5
    )
    it_gen = DeterministicCandidateGenerator(it_model, it_req)
    it_candidates = it_gen.generate_all_candidates()

    assert len(it_candidates) >= 5
    it_tools = {
        c.expected_tool_calls[-1].tool_name
        for c in it_candidates
        if c.expected_tool_calls
    }
    assert "reboot_managed_device" in it_tools or "query_device_status" in it_tools

    # Ensure different domains produce mutually exclusive tool expectations
    assert not nexa_tools.intersection(it_tools)


def test_distinct_prepared_records_produce_different_expected_bindings():
    """Verify that varying synthetic records in NexaCart refund produce distinct
    expected argument bindings (e.g. $42.50 vs $89.00) and different canonical hashes.
    """
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    nexa_req = GenerationRequest(
        config_version=1,
        case_categories=[CaseCategory.CORRECT_BEHAVIOUR],
        max_candidates=10,
    )
    generator = DeterministicCandidateGenerator(nexa_model, nexa_req)
    candidates = generator.generate_all_candidates()

    # The generator produces 2 distinct variations under CORRECT_BEHAVIOUR
    assert len(candidates) >= 2
    c1, c2 = candidates[0], candidates[1]

    # Inspect the amount argument constraints
    c1_amount = next(
        a.expected_value
        for call in c1.expected_tool_calls
        for a in call.argument_constraints
        if a.argument_name == "amount"
    )
    c2_amount = next(
        a.expected_value
        for call in c2.expected_tool_calls
        for a in call.argument_constraints
        if a.argument_name == "amount"
    )

    assert c1_amount == 42.50
    assert c2_amount == 89.00
    assert c1.canonical_hash != c2.canonical_hash


def test_candidate_validation_detects_unsupported_tools():
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model, GenerationRequest(config_version=1)
    )
    candidates = generator.generate_all_candidates()

    candidate = candidates[0]
    # Inject unsupported tool
    candidate.expected_tool_calls.append(
        ExpectedToolCallSpec(tool_name="unsupported_ghost_tool", is_forbidden=False)
    )

    issues = validate_candidate_case(candidate, nexa_model)
    assert any(i.code == "ERR_UNSUPPORTED_TOOL" for i in issues)


def test_candidate_validation_detects_contradictory_constraints():
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model, GenerationRequest(config_version=1)
    )
    candidates = generator.generate_all_candidates()

    candidate = candidates[0]
    # Mark tool as both forbidden and required (min_count > 0)
    candidate.expected_tool_calls.append(
        ExpectedToolCallSpec(
            tool_name="process_refund",
            is_forbidden=True,
            min_count=1,
        )
    )

    issues = validate_candidate_case(candidate, nexa_model)
    assert any(i.code == "ERR_CONTRADICTORY_CONSTRAINT" for i in issues)


def test_candidate_validation_detects_schema_mismatch():
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model, GenerationRequest(config_version=1)
    )
    candidates = generator.generate_all_candidates()

    candidate = candidates[0]
    # Inject unknown argument not in process_refund schema
    candidate.expected_tool_calls[-1].argument_constraints.append(
        ArgumentConstraint(
            argument_name="invalid_arg_xyz",
            presence=FieldPresence.REQUIRED_NON_NULL,
            operator=ComparisonOperator.EQUALS,
            expected_value="test",
        )
    )

    issues = validate_candidate_case(candidate, nexa_model)
    assert any(i.code == "ERR_SCHEMA_MISMATCH" for i in issues)


def test_candidate_validation_detects_unavailable_evidence_channel():
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model, GenerationRequest(config_version=1)
    )
    candidates = generator.generate_all_candidates()

    candidate = candidates[0]
    # Require an evidence channel not enabled in nexa_model (e.g. AUT_DATABASE_DIFF)
    candidate.expected_tool_calls[-1].evidence_requirements.append(
        EvidenceRequirement(channel=EvidenceChannel.AUT_DATABASE_DIFF)
    )

    issues = validate_candidate_case(candidate, nexa_model)
    assert any(i.code == "ERR_UNAVAILABLE_EVIDENCE" for i in issues)


def test_insufficient_evidence_case_does_not_invent_oracle_values():
    """Insufficient-evidence cases must document evidence limitations and avoid
    inventing arbitrary expected argument values.
    """
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model,
        GenerationRequest(
            config_version=1,
            case_categories=[CaseCategory.INSUFFICIENT_EVIDENCE],
        ),
    )
    candidates = generator.generate_all_candidates()
    assert len(candidates) >= 1
    case = candidates[0]

    assert case.category == CaseCategory.INSUFFICIENT_EVIDENCE
    assert case.evidence_limitations is not None
    assert len(case.evidence_limitations) > 0
    # Argument constraints must not invent values for untraced execution
    for call in case.expected_tool_calls:
        assert len(call.argument_constraints) == 0


def test_semantic_deduplication():
    """Verify that duplicate candidate expectation structures are detected and removed."""
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model, GenerationRequest(config_version=1)
    )
    candidates = generator.generate_all_candidates()

    # Clone the first candidate with different case_id and wording, but identical canonical hash
    dup = candidates[0].model_copy(deep=True)
    dup.case_id = "case_dup_999"
    dup.agent_task_prompt = "Superficially reworded prompt with identical expectations."

    candidates_with_dup = [candidates[0], dup, candidates[1]]

    selector = SuiteSelector(max_accepted_cases=10)
    selected, all_processed, summary, _ = selector.process_and_select(
        candidates_with_dup
    )

    assert summary.duplicates_removed == 1
    assert any(
        c.rejection_reason and "duplicate" in c.rejection_reason.lower()
        for c in all_processed
    )
    # Ensure dup was not selected
    assert "case_dup_999" not in {c.case_id for c in selected}


def test_bounded_deterministic_suite_selection():
    """Verify max_accepted_cases quota and balanced category coverage."""
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model,
        GenerationRequest(config_version=1, max_candidates=20),
    )
    candidates = generator.generate_all_candidates()
    assert len(candidates) >= 6

    # Select bounded suite with limit of 3
    selector = SuiteSelector(max_accepted_cases=3)
    selected, _, summary, content_hash = selector.process_and_select(candidates)

    assert len(selected) == 3
    assert summary.selected_count == 3
    assert len(content_hash) == 64  # Valid SHA-256 string


def test_agent_facing_task_isolation():
    """Tested agents must only receive public prompts, context inputs, and allowed tool names.
    Expectations, oracle values, and validation findings must be strictly isolated.
    """
    nexa_spec = get_nexacart_refund_example_config()
    nexa_model = _build_dummy_config_model(nexa_spec)
    generator = DeterministicCandidateGenerator(
        nexa_model, GenerationRequest(config_version=1)
    )
    candidates = generator.generate_all_candidates()

    candidate = candidates[0]
    agent_task = extract_agent_facing_task(candidate)

    # Check fields present
    assert agent_task.case_id == candidate.case_id
    assert agent_task.task_prompt == candidate.agent_task_prompt
    assert agent_task.context_inputs == candidate.task_context_inputs
    assert len(agent_task.permitted_tools) > 0

    # Ensure no expectation structures are in agent-facing task
    task_dict = agent_task.model_dump()
    assert "expected_tool_calls" not in task_dict
    assert "argument_constraints" not in task_dict
    assert "expected_value" not in task_dict
    assert "validation_issues" not in task_dict
    assert "fixture_plan" not in task_dict
