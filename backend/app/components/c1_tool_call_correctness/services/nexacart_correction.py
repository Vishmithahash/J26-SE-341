"""Code-level correction and verification for NexaCart tool code (C1 FR-09/FR-10/FR-11).

Component: C1 - Explainable Tool-Call Correctness Testing

- ``create_workspace`` makes a disposable copy of a NexaCart backend (sources, Prisma schema, build
  config, local ``.env``; ``node_modules`` linked, never copied or modified). Running copies get
  their own database and process (``nexacart_sandbox``); no containers (monolithic deployment).
- ``CONTROLLED_DEFECTS`` are the proposal's controlled defects in permitted code areas: a defect is
  seeded only into a disposable copy that runs as a separate local instance (the "defect lab"),
  never into the developer's NexaCart tree.
- ``TypeScriptMappingPatchGenerator`` produces at most one candidate patch for a diagnosed
  argument-mapping defect (an implementation that reads a key the tool schema does not declare
  instead of the declared one).
- ``NexaCartVerificationEngine`` verifies the candidate on another disposable copy with real
  checks: the original failure is recorded, the patch applies, ``nest build`` succeeds, the
  original case is re-run LIVE with NexaCart's agent against the patched build, the existing
  agent-tool Jest suite passes, and an independent acceptance case (not in the accepted suite)
  passes live. Any missing or failed step leaves the candidate UNVERIFIED.
"""

import asyncio
import difflib
import hashlib
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.correction import (
    CandidatePatch,
    CorrectionStatus,
    StepExecutionStatus,
    VerificationCheckResult,
    VerificationStepType,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    CaseCategory,
    ExpectedToolCallSpec,
    FixturePreparationPlan,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.services import nexacart_sandbox
from app.components.c1_tool_call_correctness.services.correction_engine import (
    PatchGenerationProvider,
    validate_patch_content,
)
from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
    DeterministicCorrectnessEvaluator,
)
from app.components.c1_tool_call_correctness.services.sandbox_interface import (
    DisposableIsolatedSandbox,
    apply_unified_diff_to_workspace,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    SourceInspector,
)

# Disposable NexaCart copies live here; only paths under it may be used as lab source roots.
WORKSPACE_ROOT = Path(tempfile.gettempdir()) / "c1_nexacart_workspaces"
COPY_ITEMS = (
    "src",
    "prisma",
    "package.json",
    "tsconfig.json",
    "tsconfig.build.json",
    "nest-cli.json",
    "prisma.config.ts",
    ".env",
)
# The copy gets its own database (``nexacart_sandbox.provision_database``); see that module.
BUILD_TIMEOUT_SECONDS = 420.0
JEST_TIMEOUT_SECONDS = 420.0
STARTUP_TIMEOUT_SECONDS = 90.0
# Regression scope: NexaCart's agent-tool unit and integration specs.
REGRESSION_SPEC_PATH = "src/agent-tools"


@dataclass(frozen=True)
class ControlledDefect:
    defect_id: str
    tool_name: str
    file_path: str
    function_name: str
    find: str
    replace: str
    description: str


CONTROLLED_DEFECTS: dict[str, ControlledDefect] = {
    d.defect_id: d
    for d in (
        ControlledDefect(
            defect_id="refund_order_number_mapping",
            tool_name="refund_order",
            file_path="src/agent-tools/tools/refund-order.tool.ts",
            function_name="execute",
            find="args['orderNumber']",
            replace="args['order_number']",
            description=(
                "refund_order.execute reads args['order_number'] instead of the schema argument "
                "orderNumber (argument-mapping defect): every refund is rejected as "
                "'orderNumber is required.' although the agent supplies it."
            ),
        ),
        ControlledDefect(
            defect_id="refund_order_amount_mapping",
            tool_name="refund_order",
            file_path="src/agent-tools/tools/refund-order.tool.ts",
            function_name="execute",
            find="args['amount']",
            replace="args['refund_amount']",
            description=(
                "refund_order.execute reads args['refund_amount'] instead of the schema argument "
                "amount: every refund is rejected as 'amount is required' although the agent "
                "supplies it."
            ),
        ),
        ControlledDefect(
            defect_id="add_to_cart_product_mapping",
            tool_name="add_to_cart",
            file_path="src/agent-tools/tools/add-to-cart.tool.ts",
            function_name="execute",
            find="args['productId']",
            replace="args['product_id']",
            description=(
                "add_to_cart.execute reads args['product_id'] instead of the schema argument "
                "productId: adding to the cart is rejected as 'productId must be a positive "
                "integer.' although the agent supplies it."
            ),
        ),
        ControlledDefect(
            defect_id="get_order_number_mapping",
            tool_name="get_order",
            file_path="src/agent-tools/tools/get-order.tool.ts",
            function_name="execute",
            find="args['orderNumber']",
            replace="args['order_no']",
            description=(
                "get_order.execute reads args['order_no'] instead of the schema argument "
                "orderNumber: every order lookup is rejected as 'orderNumber is required.'"
            ),
        ),
        ControlledDefect(
            defect_id="cancel_order_reason_mapping",
            tool_name="cancel_order",
            file_path="src/agent-tools/tools/cancel-order.tool.ts",
            function_name="execute",
            find="args['reason']",
            replace="args['cancel_reason']",
            description=(
                "cancel_order.execute reads args['cancel_reason'] instead of the schema argument "
                "reason: cancellations are rejected as 'reason is required for cancellation.'"
            ),
        ),
    )
}


# -- workspaces ---------------------------------------------------------------


def _link_directory(link: Path, target: Path) -> None:
    """Link node_modules into a workspace (junction on Windows, symlink elsewhere)."""
    if sys.platform.startswith("win"):
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def create_workspace(source_root: Path, label: str) -> Path:
    """Disposable copy of a NexaCart backend; the source tree is only read."""
    source_root = source_root.resolve()
    if (
        not (source_root / "package.json").is_file()
        or not (source_root / "src").is_dir()
    ):
        raise ValueError(f"'{source_root}' is not a NexaCart backend root.")
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    workspace = WORKSPACE_ROOT / f"{label}-{uuid.uuid4().hex[:8]}"
    workspace.mkdir()
    for item in COPY_ITEMS:
        src = source_root / item
        if src.is_dir():
            shutil.copytree(src, workspace / item)
        elif src.is_file():
            shutil.copy2(src, workspace / item)
    modules = source_root / "node_modules"
    if modules.is_dir():
        _link_directory(workspace / "node_modules", modules)
    return workspace


def remove_workspace(workspace: Path) -> None:
    """Delete a disposable copy (the node_modules link is removed, never its target)."""
    workspace = Path(workspace)
    try:
        workspace.resolve().relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        return  # never delete anything outside the workspace root
    nexacart_sandbox.drop_database(workspace)
    link = workspace / "node_modules"
    if link.is_symlink() or (link.exists() and os.path.isjunction(link)):
        os.unlink(link) if link.is_symlink() else os.rmdir(link)
    shutil.rmtree(workspace, ignore_errors=True)


def is_lab_workspace(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        Path(path).resolve().relative_to(WORKSPACE_ROOT.resolve())
        return True
    except ValueError:
        return False


def seed_defect(workspace: Path, defect: ControlledDefect) -> str:
    """Apply a controlled defect inside the tool's function only; returns the seeding diff."""
    target = workspace / defect.file_path
    original = target.read_text(encoding="utf-8")
    inspected = SourceInspector(workspace).inspect_function(
        defect.file_path, defect.function_name
    )
    if inspected is None:
        raise ValueError(
            f"Function '{defect.function_name}' not found in {defect.file_path}."
        )
    lines = original.splitlines(keepends=True)
    start, end = inspected.line_start - 1, inspected.line_end
    body = "".join(lines[start:end])
    if defect.find not in body:
        raise ValueError(
            f"Defect anchor {defect.find!r} not found in {defect.function_name}."
        )
    seeded = (
        "".join(lines[:start])
        + body.replace(defect.find, defect.replace)
        + "".join(lines[end:])
    )
    target.write_text(seeded, encoding="utf-8")
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            seeded.splitlines(keepends=True),
            fromfile=f"a/{defect.file_path}",
            tofile=f"b/{defect.file_path}",
        )
    )


# -- local NexaCart instances ---------------------------------------------------


def free_port(start: int = 3201, end: int = 3299) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port for a NexaCart instance.")


async def run_command(
    workspace: Path, command: list[str], timeout_seconds: float
) -> tuple[int, str, float]:
    """Run a fixed command in the workspace with secrets stripped from the environment."""
    result = await DisposableIsolatedSandbox().execute_command(
        workspace, command, timeout_seconds=timeout_seconds
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.exit_code, output[-4000:], result.duration_ms


def node_command(workspace: Path, script: str, *args: str) -> list[str]:
    return ["node", str(workspace / "node_modules" / script), *args]


class NexaCartInstance:
    """A NexaCart build started from a workspace on a local port.

    Runs as its own process group with the isolated environment and the copy's own ``.env``
    (dedicated database, see ``nexacart_sandbox``). Identified by PID so a lab can be re-adopted
    after the QA backend restarts.
    """

    def __init__(self, workspace: Path, port: int, pid: int | None = None):
        self.workspace = workspace
        self.port = port
        self.pid = pid
        self.log_path = workspace / f"instance-{port}.log"

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}/api/v1"

    def start(self) -> None:
        env = nexacart_sandbox.isolated_environment(
            self.workspace, {"PORT": str(self.port)}
        )
        self.pid = nexacart_sandbox.start_detached(
            self.workspace, ["node", "dist/src/main.js"], env, self.log_path
        )

    def is_alive(self) -> bool:
        return nexacart_sandbox.pid_alive(self.pid)

    def is_healthy(self) -> bool:
        try:
            return httpx.get(f"{self.base_url}/health", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    def wait_healthy(self, timeout: float = STARTUP_TIMEOUT_SECONDS) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.pid is not None and not self.is_alive():
                return False
            if self.is_healthy():
                return True
            time.sleep(1.0)
        return False

    def stop(self) -> None:
        nexacart_sandbox.stop_pid(self.pid)
        self.pid = None


# -- candidate patch -----------------------------------------------------------


def _normalise(name: str) -> str:
    return name.replace("_", "").replace("-", "").lower()


class TypeScriptMappingPatchGenerator(PatchGenerationProvider):
    """One deterministic patch for a diagnosed TypeScript argument-mapping defect.

    In the diagnosed function, a key the implementation reads but the schema does not declare is
    replaced by the schema argument it most closely names (and that the agent supplied).
    """

    def generate_candidate_patch(
        self,
        diagnosis: CaseDiagnosisRecord,
        candidate_location: CandidateCodeLocation,
        source_root_path: Path,
        tool_definition: ToolDefinition | None = None,
    ) -> CandidatePatch | None:
        if diagnosis.cause_category != CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT:
            return None
        if tool_definition is None or not candidate_location.file_path.endswith(
            (".ts", ".js")
        ):
            return None
        inspected = SourceInspector(source_root_path).inspect_function(
            candidate_location.file_path, candidate_location.function_name
        )
        if inspected is None:
            return None
        schema = set(tool_definition.parameters_schema.properties)
        unread = sorted(schema - set(inspected.parameters))
        undeclared = sorted(set(inspected.parameters) - schema)
        replacements: dict[str, str] = {}
        for wrong in undeclared:
            best = max(
                unread,
                key=lambda s: difflib.SequenceMatcher(
                    None, _normalise(wrong), _normalise(s)
                ).ratio(),
                default=None,
            )
            if best is not None and (
                difflib.SequenceMatcher(
                    None, _normalise(wrong), _normalise(best)
                ).ratio()
                >= 0.6
                or _normalise(best) in _normalise(wrong)
            ):
                replacements[wrong] = best
        if not replacements:
            return None

        target = source_root_path / candidate_location.file_path
        original = target.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        start, end = inspected.line_start - 1, inspected.line_end
        body = "".join(lines[start:end])
        for wrong, right in replacements.items():
            body = re.sub(
                rf"(\bargs\s*\[\s*['\"]){re.escape(wrong)}(['\"]\s*\])",
                rf"\g<1>{right}\g<2>",
                body,
            )
            body = re.sub(rf"(\bargs\.){re.escape(wrong)}\b", rf"\g<1>{right}", body)
        patched = "".join(lines[:start]) + body + "".join(lines[end:])
        if patched == original:
            return None
        rel = candidate_location.file_path.replace("\\", "/")
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                patched.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
        ok, _err, files, adds, dels = validate_patch_content(diff, allowed_paths=[rel])
        if not ok:
            return None
        return CandidatePatch(
            patch_id=f"patch_{uuid.uuid4().hex[:12]}",
            diff_content=diff,
            patch_hash=hashlib.sha256(diff.encode("utf-8")).hexdigest(),
            modified_files=files,
            additions_count=adds,
            deletions_count=dels,
            rationale=(
                f"In {inspected.function_name} ({rel}), read the schema argument(s) "
                + ", ".join(f"'{r}' instead of '{w}'" for w, r in replacements.items())
                + f" so the implementation matches the {tool_definition.name} tool schema."
            ),
        )


# -- live case execution without persistence --------------------------------------


def run_case_live(
    adapter: Any,
    case: dict[str, Any],
    tool_constraints: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run one frozen suite case with NexaCart's agent and evaluate it (same steps as a run)."""
    session_id = f"verify_{uuid.uuid4().hex[:8]}"
    fixture_service = adapter.fixture_service
    plan = FixturePreparationPlan.model_validate(case.get("fixture_plan", {}))
    ok, session_data, _ = fixture_service.prepare_fixture(session_id, plan)
    if not ok:
        return {
            "verdict": None,
            "error": fixture_service.last_error or "fixture failed",
        }
    try:
        expectations = [
            ExpectedToolCallSpec.model_validate(s)
            for s in case.get("expected_tool_calls", [])
        ]
        task, task_error = adapter.prepare_task(
            AgentFacingTask(
                case_id=case["case_id"],
                task_prompt=case.get("agent_task_prompt", ""),
                context_inputs=case.get("task_context_inputs", {}),
            ),
            session_data,
        )
        if task_error:
            return {"verdict": None, "error": task_error}
        resolved = fixture_service.resolve_expectation_values(
            expectations, session_data
        )
        result = adapter.execute_task(session_id, task)
        if result.execution_status == CaseExecutionStatus.EXECUTION_ERROR:
            return {
                "verdict": None,
                "error": result.error_message,
                "agent_run_id": result.raw_trace.get("agent_run_id"),
            }
        verdict, checks = DeterministicCorrectnessEvaluator().evaluate_case(
            case_id=case["case_id"],
            category=CaseCategory(case.get("category", "CORRECT_BEHAVIOUR")),
            resolved_expectations=resolved,
            captured_events=result.events,
            trace_completeness=result.trace_completeness,
            context_data=session_data,
            requirement_refs=case.get("requirement_refs", []),
            tool_constraints=tool_constraints,
        )
        return {
            "verdict": verdict,
            "agent_run_id": result.raw_trace.get("agent_run_id"),
            "task": task.task_prompt,
            "calls": [
                f"#{e.call_index} {e.tool_name} {e.status.value}"
                + (f" ({e.tool_error})" if e.tool_error else "")
                for e in result.events
            ],
            "failed_checks": [
                f"{c.rule_name}: {c.reason_code}"
                for c in checks
                if c.verdict != CorrectnessVerdict.PASS
            ],
        }
    finally:
        try:
            fixture_service.reset_session(session_id)
        except Exception:  # noqa: BLE001, S110 - release failure does not change evidence
            pass


def _defect_still_present(
    source_root: Path, location: CandidateCodeLocation, tool: ToolDefinition
) -> bool:
    inspected = SourceInspector(source_root).inspect_function(
        location.file_path, location.function_name
    )
    if inspected is None:
        return False
    return bool(set(tool.parameters_schema.properties) - set(inspected.parameters))


# -- verification ----------------------------------------------------------------

# The agent is stochastic: a live step passes when one of up to LIVE_ATTEMPTS fresh runs passes
# with the unchanged acceptance rules (pass@k); every attempt is recorded.
LIVE_ATTEMPTS = 3


async def _live_attempts(
    adapter: Any, case: dict[str, Any], tool_constraints: dict[str, Any] | None
) -> tuple[bool, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for _ in range(LIVE_ATTEMPTS):
        result = await asyncio.to_thread(run_case_live, adapter, case, tool_constraints)
        verdict = result.pop("verdict", None)
        attempts.append({"verdict": getattr(verdict, "value", verdict), **result})
        if verdict == CorrectnessVerdict.PASS:
            return True, attempts
        if verdict is None:  # infrastructure error: no verdict, do not retry blindly
            break
    return False, attempts


def _describe(attempts: list[dict[str, Any]]) -> str:
    parts = []
    for i, a in enumerate(attempts, start=1):
        text = f"attempt {i}: {a.get('verdict') or 'no verdict'} (agent run {a.get('agent_run_id')})"
        if a.get("failed_checks"):
            text += f" failed checks {a['failed_checks']}"
        if a.get("error"):
            text += f" error {a['error']}"
        parts.append(text)
    return "; ".join(parts)


class NexaCartVerificationEngine:
    """Six mandatory steps; ``on_step`` receives each result as soon as it is known."""

    def __init__(self, adapter_factory: Callable[[str], Any]):
        self.adapter_factory = adapter_factory

    async def execute_plan(
        self,
        source_root: Path,
        candidate_patch: CandidatePatch,
        diagnosis: CaseDiagnosisRecord,
        tool_definition: ToolDefinition,
        original_case: dict[str, Any],
        original_verdict: str | None,
        acceptance_case: dict[str, Any] | None,
        tool_constraints: dict[str, Any] | None,
        on_step: Callable[[VerificationCheckResult], None] | None = None,
    ) -> tuple[bool, CorrectionStatus, list[VerificationCheckResult], dict[str, Any]]:
        results: list[VerificationCheckResult] = []
        details: dict[str, Any] = {}

        def record(
            step: VerificationStepType,
            passed: bool,
            expected: str,
            observed: str,
            started: float,
            exit_code: int | None = None,
            extra: dict[str, Any] | None = None,
            status: StepExecutionStatus | None = None,
        ) -> bool:
            result = VerificationCheckResult(
                step_type=step,
                status=status
                or (
                    StepExecutionStatus.PASSED if passed else StepExecutionStatus.FAILED
                ),
                is_mandatory=True,
                expected_outcome=expected,
                observed_outcome=observed,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 1),
                exit_code=exit_code if exit_code is not None else (0 if passed else 1),
                details=extra or {},
            )
            results.append(result)
            if on_step:
                on_step(result)
            return passed

        def unverified() -> tuple[
            bool, CorrectionStatus, list[VerificationCheckResult], dict[str, Any]
        ]:
            return False, CorrectionStatus.UNVERIFIED, results, details

        location = min(
            diagnosis.candidate_code_locations, key=lambda c: c.ranking_score
        )

        # 1. The recorded failure and the diagnosed defect exist on the unpatched code.
        t = time.perf_counter()
        present = _defect_still_present(source_root, location, tool_definition)
        if not record(
            VerificationStepType.REPRODUCE_ORIGINAL_FAILURE,
            original_verdict
            in (CorrectnessVerdict.FAIL.value, CorrectnessVerdict.INCONCLUSIVE.value)
            and present,
            "The original live case recorded the rejected call(s) and the unpatched code still has "
            "the diagnosed mapping defect.",
            f"Original live verdict {original_verdict}; defect present in {location.file_path}: {present}.",
            t,
        ):
            return unverified()

        workspace = create_workspace(source_root, "verify")
        instance: NexaCartInstance | None = None
        details["workspace"] = str(workspace)
        try:
            # 2. Apply the candidate to the disposable copy.
            t = time.perf_counter()
            applied, err = apply_unified_diff_to_workspace(
                workspace, candidate_patch.diff_content
            )
            fixed = applied and not _defect_still_present(
                workspace, location, tool_definition
            )
            if not record(
                VerificationStepType.APPLY_PATCH,
                fixed,
                "The patch applies to the disposable copy and removes the schema/implementation mismatch.",
                f"Applied to {candidate_patch.modified_files}; mismatch removed: {fixed}"
                + (f" ({err})" if err else ""),
                t,
            ):
                return unverified()

            # 3. Real build of the patched copy.
            t = time.perf_counter()
            code, output, _ = await run_command(
                workspace,
                node_command(workspace, "@nestjs/cli/bin/nest.js", "build"),
                BUILD_TIMEOUT_SECONDS,
            )
            if not record(
                VerificationStepType.BUILD_STATIC_CHECK,
                code == 0,
                "`nest build` (TypeScript compile) of the patched NexaCart copy succeeds.",
                "Build succeeded." if code == 0 else f"Build failed (exit {code}).",
                t,
                exit_code=code,
                extra={"output_tail": output[-1500:]},
            ):
                return unverified()

            # 4. Re-run the original case live on the patched build.
            t = time.perf_counter()
            try:
                details["sandbox_database"] = await nexacart_sandbox.provision_database(
                    workspace
                )
            except Exception as exc:  # noqa: BLE001
                record(
                    VerificationStepType.RERUN_ORIGINAL_CASE,
                    False,
                    "The patched build runs on its own sandbox database and the original case passes live.",
                    f"Sandbox database could not be prepared: {exc}",
                    t,
                )
                return unverified()
            port = free_port()
            instance = NexaCartInstance(workspace, port)
            instance.start()
            healthy = await asyncio.to_thread(instance.wait_healthy)
            if not healthy:
                record(
                    VerificationStepType.RERUN_ORIGINAL_CASE,
                    False,
                    "The patched build starts and the original case passes live.",
                    f"Patched NexaCart did not become healthy on port {port}.",
                    t,
                )
                return unverified()
            adapter = self.adapter_factory(instance.base_url)
            ready, reason = await asyncio.to_thread(adapter.check_readiness)
            if ready:
                passed, attempts = await _live_attempts(
                    adapter, original_case, tool_constraints
                )
            else:
                passed, attempts = False, [{"verdict": None, "error": reason}]
            details["rerun"] = {"attempts": attempts}
            if not record(
                VerificationStepType.RERUN_ORIGINAL_CASE,
                passed,
                "The original failing case evaluates PASS live (NexaCart's agent, fresh fixture, "
                f"patched build, unchanged rules) in one of up to {LIVE_ATTEMPTS} runs.",
                f"Live rerun on {instance.base_url}: " + _describe(attempts),
                t,
                extra=details["rerun"],
            ):
                return unverified()

            # 5. Existing NexaCart regression specs for agent tools.
            t = time.perf_counter()
            code, output, _ = await run_command(
                workspace,
                node_command(workspace, "jest/bin/jest.js", REGRESSION_SPEC_PATH),
                JEST_TIMEOUT_SECONDS,
            )
            summary = next(
                (line for line in output.splitlines() if line.startswith("Tests:")), ""
            )
            if not record(
                VerificationStepType.RUN_REGRESSION_CHECKS,
                code == 0,
                f"NexaCart Jest regression specs under {REGRESSION_SPEC_PATH} pass on the patched copy.",
                f"jest exit {code}. {summary}".strip(),
                t,
                exit_code=code,
                extra={"output_tail": output[-1500:]},
            ):
                return unverified()

            # 6. Independent acceptance case (not part of the accepted suite) live.
            t = time.perf_counter()
            if acceptance_case is None:
                record(
                    VerificationStepType.RUN_INDEPENDENT_ACCEPTANCE,
                    False,
                    "An independent acceptance case for the same tool passes live.",
                    "No independent acceptance case could be generated for this tool.",
                    t,
                    status=StepExecutionStatus.BLOCKED,
                )
                return unverified()
            passed, attempts = await _live_attempts(
                adapter, acceptance_case, tool_constraints
            )
            details["acceptance"] = {
                "case_id": acceptance_case["case_id"],
                "attempts": attempts,
            }
            if not record(
                VerificationStepType.RUN_INDEPENDENT_ACCEPTANCE,
                passed,
                "An independent acceptance case for the same tool (held out of the suite) passes "
                f"live in one of up to {LIVE_ATTEMPTS} runs.",
                f"Case {acceptance_case['case_id']}: " + _describe(attempts),
                t,
                extra=details["acceptance"],
            ):
                return unverified()
            return True, CorrectionStatus.VERIFIED, results, details
        finally:
            if instance is not None:
                await asyncio.to_thread(instance.stop)
            await asyncio.to_thread(remove_workspace, workspace)


def acceptance_case_for(
    config: Any, tool_name: str, suite_case_ids: set[str], suite_hashes: set[str]
) -> dict[str, Any] | None:
    """A generated case for the same tool that is not in the accepted suite (held-out check)."""
    from app.components.c1_tool_call_correctness.contracts.generation import (
        GenerationRequest,
    )
    from app.components.c1_tool_call_correctness.services.nexacart_live_generator import (
        NexaCartLiveCandidateGenerator,
        validate_nexacart_live_case,
    )

    candidates = []
    for seed in (1013, 2027, 3041):
        for case in NexaCartLiveCandidateGenerator(
            config, GenerationRequest(seed=seed, max_candidates=50)
        ).generate_all_candidates():
            required = {
                s.tool_name
                for s in case.expected_tool_calls
                if not s.is_forbidden and s.min_count > 0
            }
            if tool_name not in required or case.canonical_hash in suite_hashes:
                continue
            if any(
                i.severity.value == "ERROR" for i in validate_nexacart_live_case(case)
            ):
                continue
            data = case.model_dump(mode="json")
            data["case_id"] = f"acceptance_{case.case_id}_s{seed}"
            if data["case_id"] not in suite_case_ids:
                candidates.append(data)
    # Prefer a plain correct-behaviour case: it isolates the repaired tool from harder reasoning.
    candidates.sort(key=lambda c: c["category"] != CaseCategory.CORRECT_BEHAVIOUR.value)
    return candidates[0] if candidates else None


def host_is_local(base_url: str) -> bool:
    return urlparse(base_url).hostname in ("localhost", "127.0.0.1", "::1")
