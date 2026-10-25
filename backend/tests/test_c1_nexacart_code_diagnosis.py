"""C1 code-level diagnosis, correction and repetitions for NexaCart (hermetic).

The TypeScript tool source below mirrors NexaCart's ``refund-order.tool.ts`` shape. Real builds,
Jest and live reruns are exercised by the live defect-lab check (see README section 5C).
"""

from pathlib import Path

from app.components.c1_tool_call_correctness.contracts.configuration import (
    CodeMapping,
    ToolDefinition,
    ToolParameterSchema,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import CauseCategory
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    CaseExecutionDetail,
    EventStatus,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
)
from app.components.c1_tool_call_correctness.services import nexacart_correction
from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
    DeterministicCorrectnessEvaluator,
)
from app.components.c1_tool_call_correctness.services.diagnosis_engine import (
    DiagnosisEngine,
)
from app.components.c1_tool_call_correctness.services.explanation_engine import (
    ExplanationEngine,
)
from app.components.c1_tool_call_correctness.services.nexacart_correction import (
    CONTROLLED_DEFECTS,
    TypeScriptMappingPatchGenerator,
    create_workspace,
    remove_workspace,
    seed_defect,
)
from app.components.c1_tool_call_correctness.services.sandbox_interface import (
    apply_unified_diff_to_workspace,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    SourceInspector,
)

TOOL_FILE = "src/agent-tools/tools/refund-order.tool.ts"
TOOL_SOURCE = """import { Injectable } from '@nestjs/common';

@Injectable()
export class RefundOrderTool implements AgentTool {
  readonly name = 'refund_order';

  idempotencyKeyFor(args: Record<string, unknown>): string | undefined {
    const orderNumber = typeof args['orderNumber'] === 'string' ? args['orderNumber'] : '';
    return orderNumber || undefined;
  }

  /** Refund a cancelled, paid order. */
  async execute(
    args: Record<string, unknown>,
    context: AgentExecutionContext,
  ): Promise<StandardToolResultEnvelope> {
    const orderNumber =
      typeof args['orderNumber'] === 'string' ? args['orderNumber'].trim() : '';
    const amount = typeof args['amount'] === 'string' ? args['amount'].trim() : '';
    const reason = typeof args["reason"] === 'string' ? args.reason.trim() : '';
    if (!orderNumber) {
      return { ok: false, error: { errorCode: 'AGENT_TOOL_INVALID_ARGUMENTS', message: 'orderNumber is required.', statusCode: 400 } };
    }
    // a brace in a string: '}' must not end the method
    return { ok: true, data: { orderNumber, amount, reason, note: '}' } };
  }
}
"""

REFUND_TOOL = ToolDefinition(
    name="refund_order",
    description="Refund a cancelled order.",
    parameters_schema=ToolParameterSchema(
        properties={
            "orderNumber": {"type": "string"},
            "amount": {"type": "string"},
            "reason": {"type": "string"},
        },
        required=["orderNumber", "amount", "reason"],
    ),
    code_mapping=CodeMapping(file_path=TOOL_FILE, function_name="execute"),
)


def _nexacart_tree(root: Path, source: str = TOOL_SOURCE) -> Path:
    (root / "src/agent-tools/tools").mkdir(parents=True)
    (root / TOOL_FILE).write_text(source, encoding="utf-8")
    (root / "package.json").write_text('{"name": "backend"}', encoding="utf-8")
    return root


def _failed_refund_case(error: str, status_code: int) -> CaseExecutionDetail:
    event = CapturedToolEvent(
        event_id="nxc-call-1",
        call_index=1,
        tool_name="refund_order",
        arguments={"orderNumber": "NXC-QA-1-1", "amount": "40.00", "reason": "damaged"},
        status=EventStatus.FAILED,
        tool_error=error,
        tool_response={
            "ok": False,
            "error": {"message": error, "statusCode": status_code},
        },
    )
    expectations = [
        ExpectedToolCallSpec(tool_name="refund_order", min_count=1, max_count=1)
    ]
    verdict, checks = DeterministicCorrectnessEvaluator().evaluate_case(
        case_id="c1",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=expectations,
        captured_events=[event],
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data={},
        requirement_refs=[],
    )
    return CaseExecutionDetail(
        execution_id="cexec-1",
        case_id="c1",
        session_id="s1",
        readiness_status=CaseReadinessStatus.CONFIGURED,
        execution_status=CaseExecutionStatus.EXECUTED,
        verdict=verdict,
        resolved_expectations=expectations,
        captured_events=[event],
        check_results=checks,
    )


def _diagnose(root: Path, case: CaseExecutionDetail):
    explanations = ExplanationEngine().explain_case_checks(
        check_results=case.check_results,
        captured_events=case.captured_events,
        trace_completeness=case.trace_completeness,
    )
    return DiagnosisEngine().diagnose_case(
        project_id="p",
        run_id="r",
        case_execution=case,
        check_explanations=explanations,
        tool_definitions={"refund_order": REFUND_TOOL},
        source_inspector=SourceInspector(root),
    )


def test_typescript_inspection_reports_keys_read_by_the_method(tmp_path):
    root = _nexacart_tree(tmp_path / "nxc")
    found = SourceInspector(root).inspect_function(TOOL_FILE, "execute")
    assert found.parameters == ["amount", "orderNumber", "reason"]
    assert found.line_start == 13
    assert TOOL_SOURCE.splitlines()[found.line_end - 1].strip() == "}"
    assert found.docstring == "Refund a cancelled, paid order."


def test_seeded_mapping_defect_is_localised_as_code_defect(tmp_path):
    root = _nexacart_tree(
        tmp_path / "nxc",
        TOOL_SOURCE.replace(
            "args['orderNumber'] === 'string' ? args['orderNumber'].trim()",
            "args['order_number'] === 'string' ? args['order_number'].trim()",
        ),
    )
    diagnosis = _diagnose(root, _failed_refund_case("orderNumber is required.", 400))
    assert diagnosis.cause_category == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
    location = diagnosis.candidate_code_locations[0]
    assert (location.file_path, location.function_name) == (TOOL_FILE, "execute")
    assert "never reads them" in diagnosis.explanation_summary
    assert "order_number" in diagnosis.explanation_summary


def test_business_rejection_is_not_blamed_on_code(tmp_path):
    root = _nexacart_tree(tmp_path / "nxc")
    diagnosis = _diagnose(
        root, _failed_refund_case("Refund requires a cancelled order.", 400)
    )
    assert diagnosis.cause_category == CauseCategory.AGENT_BEHAVIOUR
    assert diagnosis.candidate_code_locations == []


def test_patch_generator_restores_the_schema_argument(tmp_path):
    seeded = TOOL_SOURCE.replace(
        "args['orderNumber'] === 'string' ? args['orderNumber'].trim()",
        "args['order_number'] === 'string' ? args['order_number'].trim()",
    )
    root = _nexacart_tree(tmp_path / "nxc", seeded)
    diagnosis = _diagnose(root, _failed_refund_case("orderNumber is required.", 400))
    patch = TypeScriptMappingPatchGenerator().generate_candidate_patch(
        diagnosis, diagnosis.candidate_code_locations[0], root, REFUND_TOOL
    )
    assert patch is not None and patch.modified_files == [TOOL_FILE]
    assert (
        "+      typeof args['orderNumber'] === 'string' ? args['orderNumber'].trim()"
        in patch.diff_content
    )
    # the method outside the diagnosed function is untouched
    assert "idempotencyKeyFor" not in patch.diff_content
    ok, err = apply_unified_diff_to_workspace(root, patch.diff_content)
    assert ok, err
    assert (root / TOOL_FILE).read_text(encoding="utf-8") == TOOL_SOURCE


def test_workspace_seed_and_cleanup_never_touch_the_source(tmp_path, monkeypatch):
    monkeypatch.setattr(nexacart_correction, "WORKSPACE_ROOT", tmp_path / "ws")
    source = _nexacart_tree(tmp_path / "nxc")
    workspace = create_workspace(source, "lab")
    diff = seed_defect(workspace, CONTROLLED_DEFECTS["refund_order_number_mapping"])
    assert "args['order_number']" in diff
    assert "args['order_number']" in (workspace / TOOL_FILE).read_text(encoding="utf-8")
    assert (source / TOOL_FILE).read_text(encoding="utf-8") == TOOL_SOURCE
    # idempotencyKeyFor keeps the schema key: the defect is seeded inside execute only
    assert "args['orderNumber'] === 'string' ? args['orderNumber'] : ''" in (
        workspace / TOOL_FILE
    ).read_text(encoding="utf-8")
    remove_workspace(source)  # outside the workspace root: refused
    assert (source / TOOL_FILE).is_file()
    remove_workspace(workspace)
    assert not workspace.exists()


def test_self_corrected_rejected_call_is_explained():
    events = [
        CapturedToolEvent(
            event_id="e1",
            call_index=1,
            tool_name="refund_order",
            arguments={"orderNumber": "QA-1-Desk Lamp"},
            status=EventStatus.FAILED,
            tool_error="Order not found.",
        ),
        CapturedToolEvent(
            event_id="e2",
            call_index=3,
            tool_name="refund_order",
            arguments={"orderNumber": "NXC-QA-1-1"},
            status=EventStatus.SUCCESS,
        ),
    ]
    verdict, checks = DeterministicCorrectnessEvaluator().evaluate_case(
        case_id="c",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[
            ExpectedToolCallSpec(tool_name="refund_order", min_count=1, max_count=1)
        ],
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data={},
        requirement_refs=[],
    )
    assert verdict.value == "FAIL"
    count = next(c for c in checks if c.rule_name == "TOOL_INVOCATION_COUNT")
    assert count.reason_code == "SELF_CORRECTED_AFTER_REJECTED_CALL"
    assert "Order not found." in count.explanation
    explanation = ExplanationEngine().explain_case_checks(
        check_results=checks,
        captured_events=events,
        trace_completeness=TraceCompleteness.COMPLETE,
    )
    assert explanation[0].what_was_observed.startswith("Self-corrected")


def test_recorded_rejection_is_a_code_defect_even_when_the_run_did_not_finish(tmp_path):
    root = _nexacart_tree(
        tmp_path / "nxc",
        TOOL_SOURCE.replace(
            "args['orderNumber'] === 'string' ? args['orderNumber'].trim()",
            "args['order_number'] === 'string' ? args['order_number'].trim()",
        ),
    )
    case = _failed_refund_case("orderNumber is required.", 400).model_copy(
        update={
            "execution_status": CaseExecutionStatus.EXECUTION_ERROR,
            "trace_completeness": TraceCompleteness.INCOMPLETE,
        }
    )
    diagnosis = _diagnose(root, case)
    assert diagnosis.cause_category == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
    assert "rests only on the recorded rejected call" in diagnosis.explanation_summary
    # without the mismatch, an unfinished run stays UNKNOWN
    clean = _nexacart_tree(tmp_path / "clean")
    assert _diagnose(clean, case).cause_category == CauseCategory.UNKNOWN
