"""Business logic, readiness evaluation, and persistence for Shared Integration.

Component: Shared Integration Foundation (Part 1)
Responsibilities:
- Deterministic cross-component readiness assessment.
- Freezing referenced model/case/contract versions and digests.
- Rejection of cross-project references and mutable references.
- Maintenance of native-to-shared identifier mappings.
- Persistent run plan lifecycle management without launching operations.
"""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.expectations import (
    ExpectationSuite,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2TestCase,
    C2TestSuite,
    C2WorkflowModel,
)
from app.components.c3_robustness_recovery.models.persistence import (
    C3SuiteModel,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyRule,
)
from app.components.c4_policy_aware_safety.persistence.models import (
    C4ContractModel,
)
from app.shared.auth.models import User
from app.shared.integration.contracts import (
    ComponentReadinessIssue,
    ComponentReadinessSummary,
    ComponentReferencesPlan,
    ComponentType,
    CorrelationMapping,
    IntegrationPlanListResponse,
    IntegrationPlanStatus,
    IntegrationReadinessReport,
    IntegrationRunPlanCreateRequest,
    IntegrationRunPlanResponse,
    NativeEntityType,
    ReadinessIssueCode,
    ReadinessSeverity,
    ReadinessVerdict,
)
from app.shared.integration.models import (
    IntegrationIdentifierMappingModel,
    IntegrationRunPlanModel,
)
from app.shared.projects.models import Project

logger = logging.getLogger(__name__)


def canonical_json_digest(data: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest over canonical JSON bytes."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def resolve_c1_expectations_from_snapshot(
    config_expectations: dict[str, Any] | None,
    tool_constraints: dict[str, Any] | None = None,
    suite_case: dict[str, Any] | None = None,
) -> tuple[list[ExpectedToolCallSpec], str | None, list[str], str]:
    """Resolve declarative C1 expectations and tool constraints into ExpectedToolCallSpecs.

    Reuses C1 native ExpectationSuite and Case structures. Never falls back arbitrarily to order_placement.
    Returns: (expected_tool_calls, case_id, requirement_refs, category)
    """
    if suite_case:
        raw_specs = suite_case.get("expected_tool_calls", [])
        expected_calls = [
            ExpectedToolCallSpec.model_validate(s) if isinstance(s, dict) else s
            for s in raw_specs
        ]
        case_id = suite_case.get("case_id")
        req_refs = suite_case.get("requirement_refs", [])
        category = suite_case.get("category", CaseCategory.CORRECT_BEHAVIOUR.value)
        return expected_calls, case_id, req_refs, category

    tc_dict = tool_constraints or {}
    max_inv = tc_dict.get("max_invocations", {})
    forbidden = set(tc_dict.get("forbidden_tools", []))
    required = set(tc_dict.get("required_tools", []))

    expected_calls = []
    seen_tools: set[str] = set()

    if config_expectations and isinstance(config_expectations, dict):
        try:
            suite = ExpectationSuite.model_validate(config_expectations)
            for sel in suite.tool_selections:
                tool_name = sel.tool_name
                seen_tools.add(tool_name)
                is_forbid = (tool_name in forbidden) or (
                    not sel.is_required and sel.max_count == 0
                )
                min_c = 0 if is_forbid else (sel.min_count if sel.is_required else 0)
                max_c = 0 if is_forbid else (max_inv.get(tool_name, sel.max_count))
                args = suite.argument_constraints.get(tool_name, [])
                evs = [
                    ev
                    for ev in suite.evidence_requirements
                    if not ev.required_for_checks or tool_name in ev.required_for_checks
                ]
                expected_calls.append(
                    ExpectedToolCallSpec(
                        tool_name=tool_name,
                        is_forbidden=is_forbid,
                        min_count=min_c,
                        max_count=max_c,
                        must_precede_tools=sel.must_precede_tools,
                        argument_constraints=args,
                        evidence_requirements=evs,
                        requirement_refs=sel.requirement_refs,
                    )
                )
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("Could not parse C1 ExpectationSuite from config: %s", exc)

    for f_tool in forbidden:
        if f_tool not in seen_tools:
            seen_tools.add(f_tool)
            expected_calls.append(
                ExpectedToolCallSpec(
                    tool_name=f_tool,
                    is_forbidden=True,
                    min_count=0,
                    max_count=0,
                )
            )

    for r_tool in required:
        if r_tool not in seen_tools:
            seen_tools.add(r_tool)
            expected_calls.append(
                ExpectedToolCallSpec(
                    tool_name=r_tool,
                    is_forbidden=False,
                    min_count=1,
                    max_count=max_inv.get(r_tool, 1),
                )
            )

    return expected_calls, None, [], CaseCategory.CORRECT_BEHAVIOUR.value


class IntegrationService:
    """Service providing readiness assessment, intake validation, and plan persistence."""

    def __init__(self, db: Session):
        self.db = db

    def check_readiness(
        self,
        project_id: str,
        references: ComponentReferencesPlan,
    ) -> IntegrationReadinessReport:
        """Evaluate integration readiness deterministically against persisted component states.

        Enforces:
        1. No cross-project references allowed.
        2. Component configurations must exist in the database.
        3. Models/contracts must have approved/frozen status.
        4. Missing component configurations produce explicit readiness reasons.
        """
        blocking_issues: list[ComponentReadinessIssue] = []
        warnings: list[ComponentReadinessIssue] = []
        statuses: dict[str, ComponentReadinessSummary] = {}

        # -------------------------------------------------------------------
        # Component 1 (Tool-Call Correctness) Validation
        # -------------------------------------------------------------------
        c1_issues: list[ComponentReadinessIssue] = []
        c1_ready = False
        c1_ref_id = None
        c1_digest = None

        if references.c1 is None:
            c1_issues.append(
                ComponentReadinessIssue(
                    component=ComponentType.C1,
                    issue_code=ReadinessIssueCode.MISSING_CONFIGURATION,
                    message="Component 1 configuration reference was not provided in the run plan.",
                    severity=ReadinessSeverity.LIMITATION,
                )
            )
        else:
            c1_ref = references.c1
            if c1_ref.project_id != project_id:
                issue = ComponentReadinessIssue(
                    component=ComponentType.C1,
                    issue_code=ReadinessIssueCode.CROSS_PROJECT_REFERENCE,
                    message=(
                        f"Cross-project reference rejected: C1 reference project '{c1_ref.project_id}' "
                        f"does not match plan project '{project_id}'."
                    ),
                    severity=ReadinessSeverity.BLOCKING,
                )
                c1_issues.append(issue)
                blocking_issues.append(issue)
            else:
                # Query C1 config strictly matching project, config_id, and version together
                config = (
                    self.db.execute(
                        select(C1ProjectConfigModel).where(
                            C1ProjectConfigModel.project_id == project_id,
                            C1ProjectConfigModel.id == c1_ref.config_id,
                            C1ProjectConfigModel.version == c1_ref.config_version,
                        )
                    )
                    .scalars()
                    .first()
                )

                if not config:
                    issue = ComponentReadinessIssue(
                        component=ComponentType.C1,
                        issue_code=ReadinessIssueCode.CONFIG_NOT_FOUND,
                        message=f"C1 configuration '{c1_ref.config_id}' (v{c1_ref.config_version}) not found.",
                        severity=ReadinessSeverity.BLOCKING,
                    )
                    c1_issues.append(issue)
                    blocking_issues.append(issue)
                else:
                    c1_ref_id = config.id
                    # Compute frozen digest of C1 configuration tools & requirements
                    digest_payload = {
                        "config_id": config.id,
                        "project_id": config.project_id,
                        "version": config.version,
                        "tools": config.tools,
                        "requirements": config.requirements,
                        "tool_constraints": config.tool_constraints,
                    }
                    c1_digest = canonical_json_digest(digest_payload)
                    c1_ref.frozen_content_hash = c1_digest
                    c1_ref.agent_connection_ref = config.agent_connection_ref
                    c1_ref.tool_names = [
                        t.get("name", "")
                        for t in (config.tools or [])
                        if isinstance(t, dict)
                    ]

                    if c1_ref.suite_id:
                        suite_q = select(C1SuiteVersionModel).where(
                            C1SuiteVersionModel.project_id == project_id,
                            C1SuiteVersionModel.config_id == config.id,
                            C1SuiteVersionModel.suite_id == c1_ref.suite_id,
                        )
                        if c1_ref.suite_version is not None:
                            suite_q = suite_q.where(
                                C1SuiteVersionModel.version == c1_ref.suite_version
                            )
                        c1_suite = self.db.execute(suite_q).scalars().first()
                        if not c1_suite:
                            issue = ComponentReadinessIssue(
                                component=ComponentType.C1,
                                issue_code=ReadinessIssueCode.SUITE_NOT_FOUND,
                                message=f"C1 suite '{c1_ref.suite_id}' not found for config '{config.id}'.",
                                severity=ReadinessSeverity.BLOCKING,
                            )
                            c1_issues.append(issue)
                            blocking_issues.append(issue)
                        else:
                            cases = c1_suite.cases or []
                            if c1_ref.case_id:
                                found_c = any(
                                    (
                                        c.get("case_id")
                                        if isinstance(c, dict)
                                        else getattr(c, "case_id", None)
                                    )
                                    == c1_ref.case_id
                                    for c in cases
                                )
                                if not found_c:
                                    issue = ComponentReadinessIssue(
                                        component=ComponentType.C1,
                                        issue_code=ReadinessIssueCode.CASE_NOT_FOUND,
                                        message=f"C1 case '{c1_ref.case_id}' not found in suite '{c1_ref.suite_id}'.",
                                        severity=ReadinessSeverity.BLOCKING,
                                    )
                                    c1_issues.append(issue)
                                    blocking_issues.append(issue)
                                else:
                                    c1_ready = True
                            elif len(cases) == 0:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C1,
                                    issue_code=ReadinessIssueCode.EMPTY_SUITE,
                                    message=f"C1 suite '{c1_ref.suite_id}' contains 0 test cases.",
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c1_issues.append(issue)
                                blocking_issues.append(issue)
                            elif len(cases) > 1:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C1,
                                    issue_code=ReadinessIssueCode.AMBIGUOUS_SELECTION,
                                    message=f"C1 suite '{c1_ref.suite_id}' contains {len(cases)} cases; specific case_id must be selected.",
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c1_issues.append(issue)
                                blocking_issues.append(issue)
                            else:
                                c1_ready = True
                    else:
                        if not config.tools and not config.expectations:
                            issue = ComponentReadinessIssue(
                                component=ComponentType.C1,
                                issue_code=ReadinessIssueCode.EMPTY_SUITE,
                                message=f"C1 configuration '{config.id}' contains no tools or expectations.",
                                severity=ReadinessSeverity.BLOCKING,
                            )
                            c1_issues.append(issue)
                            blocking_issues.append(issue)
                        else:
                            c1_ready = True

        statuses[ComponentType.C1.value] = ComponentReadinessSummary(
            component=ComponentType.C1,
            is_ready=c1_ready,
            native_ref_id=c1_ref_id,
            frozen_digest=c1_digest,
            issues=c1_issues,
        )

        # -------------------------------------------------------------------
        # Component 2 (State-Aware Multi-Step Workflow) Validation
        # -------------------------------------------------------------------
        c2_issues: list[ComponentReadinessIssue] = []
        c2_ready = False
        c2_ref_id = None
        c2_digest = None

        if references.c2 is None:
            c2_issues.append(
                ComponentReadinessIssue(
                    component=ComponentType.C2,
                    issue_code=ReadinessIssueCode.MISSING_CONFIGURATION,
                    message="Component 2 model reference was not provided in the run plan.",
                    severity=ReadinessSeverity.LIMITATION,
                )
            )
        else:
            c2_ref = references.c2
            if c2_ref.project_id != project_id:
                issue = ComponentReadinessIssue(
                    component=ComponentType.C2,
                    issue_code=ReadinessIssueCode.CROSS_PROJECT_REFERENCE,
                    message=(
                        f"Cross-project reference rejected: C2 reference project '{c2_ref.project_id}' "
                        f"does not match plan project '{project_id}'."
                    ),
                    severity=ReadinessSeverity.BLOCKING,
                )
                c2_issues.append(issue)
                blocking_issues.append(issue)
            else:
                model = (
                    self.db.execute(
                        select(C2WorkflowModel).where(
                            C2WorkflowModel.project_id == project_id,
                            C2WorkflowModel.model_id == c2_ref.model_id,
                            C2WorkflowModel.version == c2_ref.model_version,
                        )
                    )
                    .scalars()
                    .first()
                )

                if not model:
                    issue = ComponentReadinessIssue(
                        component=ComponentType.C2,
                        issue_code=ReadinessIssueCode.MODEL_NOT_FOUND,
                        message=(
                            f"C2 workflow model '{c2_ref.model_id}' version '{c2_ref.model_version}' "
                            f"not found in project '{project_id}'."
                        ),
                        severity=ReadinessSeverity.BLOCKING,
                    )
                    c2_issues.append(issue)
                    blocking_issues.append(issue)
                else:
                    c2_ref_id = model.model_id
                    c2_digest = model.content_hash
                    c2_ref.frozen_content_hash = model.content_hash
                    c2_ref.lifecycle_status = model.lifecycle_status

                    if model.lifecycle_status != "APPROVED":
                        issue = ComponentReadinessIssue(
                            component=ComponentType.C2,
                            issue_code=ReadinessIssueCode.UNAPPROVED_MODEL,
                            message=(
                                f"C2 workflow model '{model.model_id}' is in lifecycle state "
                                f"'{model.lifecycle_status}'. Only APPROVED models are ready for integration runs."
                            ),
                            severity=ReadinessSeverity.BLOCKING,
                        )
                        c2_issues.append(issue)
                        blocking_issues.append(issue)
                    else:
                        test_q = (
                            select(C2TestCase)
                            .join(
                                C2TestSuite,
                                C2TestCase.suite_record_id == C2TestSuite.id,
                            )
                            .where(
                                C2TestCase.project_id == project_id,
                                C2TestSuite.model_id == c2_ref.model_id,
                                C2TestSuite.model_version == c2_ref.model_version,
                            )
                        )
                        if c2_ref.suite_id:
                            test_q = test_q.where(
                                C2TestCase.suite_id == c2_ref.suite_id
                            )
                        if c2_ref.test_id:
                            test_q = test_q.where(C2TestCase.test_id == c2_ref.test_id)

                        matched_tests = self.db.execute(test_q).scalars().all()

                        if c2_ref.test_id:
                            if not matched_tests:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C2,
                                    issue_code=ReadinessIssueCode.TEST_NOT_FOUND,
                                    message=(
                                        f"C2 test '{c2_ref.test_id}' not found for approved model '{c2_ref.model_id}' "
                                        f"(v{c2_ref.model_version})"
                                        + (
                                            f" in suite '{c2_ref.suite_id}'."
                                            if c2_ref.suite_id
                                            else "."
                                        )
                                    ),
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c2_issues.append(issue)
                                blocking_issues.append(issue)
                            elif len(matched_tests) > 1:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C2,
                                    issue_code=ReadinessIssueCode.AMBIGUOUS_SELECTION,
                                    message=(
                                        f"Multiple matching C2 tests found for test_id '{c2_ref.test_id}'. "
                                        "Specify suite_id to disambiguate."
                                    ),
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c2_issues.append(issue)
                                blocking_issues.append(issue)
                            else:
                                tc = matched_tests[0]
                                if not tc.is_ready or tc.readiness != "TEST_READY":
                                    issue = ComponentReadinessIssue(
                                        component=ComponentType.C2,
                                        issue_code=ReadinessIssueCode.TEST_NOT_READY,
                                        message=(
                                            f"C2 test '{tc.test_id}' is not ready for execution: "
                                            f"readiness='{tc.readiness}', is_ready={tc.is_ready}."
                                        ),
                                        severity=ReadinessSeverity.BLOCKING,
                                    )
                                    c2_issues.append(issue)
                                    blocking_issues.append(issue)
                                else:
                                    c2_ref.suite_id = tc.suite_id
                                    c2_ready = True
                        elif c2_ref.suite_id:
                            if not matched_tests:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C2,
                                    issue_code=ReadinessIssueCode.TEST_NOT_FOUND,
                                    message=f"No generated tests found in suite '{c2_ref.suite_id}' for model '{c2_ref.model_id}'.",
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c2_issues.append(issue)
                                blocking_issues.append(issue)
                            elif len(matched_tests) > 1:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C2,
                                    issue_code=ReadinessIssueCode.AMBIGUOUS_SELECTION,
                                    message=(
                                        f"C2 suite '{c2_ref.suite_id}' contains {len(matched_tests)} tests. "
                                        "Specific test_id must be selected."
                                    ),
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c2_issues.append(issue)
                                blocking_issues.append(issue)
                            else:
                                tc = matched_tests[0]
                                if not tc.is_ready or tc.readiness != "TEST_READY":
                                    issue = ComponentReadinessIssue(
                                        component=ComponentType.C2,
                                        issue_code=ReadinessIssueCode.TEST_NOT_READY,
                                        message=f"C2 test '{tc.test_id}' is not ready: readiness='{tc.readiness}', is_ready={tc.is_ready}.",
                                        severity=ReadinessSeverity.BLOCKING,
                                    )
                                    c2_issues.append(issue)
                                    blocking_issues.append(issue)
                                else:
                                    c2_ref.test_id = tc.test_id
                                    c2_ready = True
                        else:
                            # Neither test_id nor suite_id provided
                            if not matched_tests:
                                c2_ready = True
                            elif len(matched_tests) > 1:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C2,
                                    issue_code=ReadinessIssueCode.AMBIGUOUS_SELECTION,
                                    message=(
                                        f"Multiple generated tests ({len(matched_tests)}) exist for model '{c2_ref.model_id}'. "
                                        "Specific test_id must be selected."
                                    ),
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c2_issues.append(issue)
                                blocking_issues.append(issue)
                            else:
                                tc = matched_tests[0]
                                if not tc.is_ready or tc.readiness != "TEST_READY":
                                    issue = ComponentReadinessIssue(
                                        component=ComponentType.C2,
                                        issue_code=ReadinessIssueCode.TEST_NOT_READY,
                                        message=f"C2 test '{tc.test_id}' is not ready: readiness='{tc.readiness}', is_ready={tc.is_ready}.",
                                        severity=ReadinessSeverity.BLOCKING,
                                    )
                                    c2_issues.append(issue)
                                    blocking_issues.append(issue)
                                else:
                                    c2_ref.test_id = tc.test_id
                                    c2_ref.suite_id = tc.suite_id
                                    c2_ready = True

        statuses[ComponentType.C2.value] = ComponentReadinessSummary(
            component=ComponentType.C2,
            is_ready=c2_ready,
            native_ref_id=c2_ref_id,
            frozen_digest=c2_digest,
            issues=c2_issues,
        )

        # -------------------------------------------------------------------
        # Component 3 (Robustness and Failure Recovery) Validation
        # -------------------------------------------------------------------
        c3_issues: list[ComponentReadinessIssue] = []
        c3_ready = False
        c3_ref_id = None
        c3_digest = None

        if references.c3 is None:
            c3_issues.append(
                ComponentReadinessIssue(
                    component=ComponentType.C3,
                    issue_code=ReadinessIssueCode.MISSING_CONFIGURATION,
                    message="Component 3 fault suite reference was not provided in the run plan.",
                    severity=ReadinessSeverity.LIMITATION,
                )
            )
        else:
            c3_ref = references.c3
            if c3_ref.project_id != project_id:
                issue = ComponentReadinessIssue(
                    component=ComponentType.C3,
                    issue_code=ReadinessIssueCode.CROSS_PROJECT_REFERENCE,
                    message=(
                        f"Cross-project reference rejected: C3 reference project '{c3_ref.project_id}' "
                        f"does not match plan project '{project_id}'."
                    ),
                    severity=ReadinessSeverity.BLOCKING,
                )
                c3_issues.append(issue)
                blocking_issues.append(issue)
            else:
                suite = (
                    self.db.execute(
                        select(C3SuiteModel).where(
                            C3SuiteModel.project_id == project_id,
                            C3SuiteModel.suite_digest == c3_ref.suite_digest,
                        )
                    )
                    .scalars()
                    .first()
                )

                if not suite:
                    issue = ComponentReadinessIssue(
                        component=ComponentType.C3,
                        issue_code=ReadinessIssueCode.SUITE_NOT_FOUND,
                        message=(
                            f"C3 frozen suite with digest '{c3_ref.suite_digest}' "
                            f"not found in project '{project_id}'."
                        ),
                        severity=ReadinessSeverity.BLOCKING,
                    )
                    c3_issues.append(issue)
                    blocking_issues.append(issue)
                else:
                    if c3_ref.suite_id and c3_ref.suite_id != suite.suite_id:
                        issue = ComponentReadinessIssue(
                            component=ComponentType.C3,
                            issue_code=ReadinessIssueCode.SUITE_NOT_FOUND,
                            message=(
                                f"Contradictory C3 suite reference: supplied suite_id '{c3_ref.suite_id}' "
                                f"does not match suite '{suite.suite_id}' found for digest '{c3_ref.suite_digest}'."
                            ),
                            severity=ReadinessSeverity.BLOCKING,
                        )
                        c3_issues.append(issue)
                        blocking_issues.append(issue)
                    else:
                        c3_ref_id = suite.suite_id
                        c3_digest = suite.suite_digest
                        c3_ref.suite_id = suite.suite_id
                        c3_ref.task_id = suite.task_id
                        c3_ref.target_tool_id = suite.tool_id
                        c3_ref.total_cases = suite.total_cases

                        if suite.total_cases <= 0:
                            issue = ComponentReadinessIssue(
                                component=ComponentType.C3,
                                issue_code=ReadinessIssueCode.EMPTY_SUITE,
                                message=f"C3 suite '{suite.suite_id}' contains 0 test cases.",
                                severity=ReadinessSeverity.BLOCKING,
                            )
                            c3_issues.append(issue)
                            blocking_issues.append(issue)
                        elif c3_ref.case_id:
                            found_case = False
                            if suite.cases:
                                for c in suite.cases:
                                    c_snap = (
                                        c.case_snapshot
                                        if hasattr(c, "case_snapshot")
                                        else {}
                                    )
                                    c_id = (
                                        c_snap.get("case_id")
                                        if isinstance(c_snap, dict)
                                        else getattr(c, "case_id", None)
                                    )
                                    if c_id == c3_ref.case_id:
                                        found_case = True
                                        break
                            if not found_case:
                                issue = ComponentReadinessIssue(
                                    component=ComponentType.C3,
                                    issue_code=ReadinessIssueCode.CASE_NOT_FOUND,
                                    message=f"C3 case '{c3_ref.case_id}' not found in suite '{suite.suite_id}'.",
                                    severity=ReadinessSeverity.BLOCKING,
                                )
                                c3_issues.append(issue)
                                blocking_issues.append(issue)
                            else:
                                c3_ready = True
                        elif suite.total_cases > 1:
                            issue = ComponentReadinessIssue(
                                component=ComponentType.C3,
                                issue_code=ReadinessIssueCode.AMBIGUOUS_SELECTION,
                                message=(
                                    f"C3 suite '{suite.suite_id}' contains {suite.total_cases} cases. "
                                    "Specific case_id must be selected."
                                ),
                                severity=ReadinessSeverity.BLOCKING,
                            )
                            c3_issues.append(issue)
                            blocking_issues.append(issue)
                        else:
                            c3_ready = True

        statuses[ComponentType.C3.value] = ComponentReadinessSummary(
            component=ComponentType.C3,
            is_ready=c3_ready,
            native_ref_id=c3_ref_id,
            frozen_digest=c3_digest,
            issues=c3_issues,
        )

        # -------------------------------------------------------------------
        # Component 4 (Policy-Aware Safety) Validation
        # -------------------------------------------------------------------
        c4_issues: list[ComponentReadinessIssue] = []
        c4_ready = False
        c4_ref_id = None
        c4_digest = None

        if references.c4 is None:
            c4_issues.append(
                ComponentReadinessIssue(
                    component=ComponentType.C4,
                    issue_code=ReadinessIssueCode.MISSING_CONFIGURATION,
                    message="Component 4 policy contract reference was not provided in the run plan.",
                    severity=ReadinessSeverity.LIMITATION,
                )
            )
        else:
            c4_ref = references.c4
            if c4_ref.project_id != project_id:
                issue = ComponentReadinessIssue(
                    component=ComponentType.C4,
                    issue_code=ReadinessIssueCode.CROSS_PROJECT_REFERENCE,
                    message=(
                        f"Cross-project reference rejected: C4 reference project '{c4_ref.project_id}' "
                        f"does not match plan project '{project_id}'."
                    ),
                    severity=ReadinessSeverity.BLOCKING,
                )
                c4_issues.append(issue)
                blocking_issues.append(issue)
            else:
                if c4_ref.contract_id and c4_ref.contract_version is None:
                    issue = ComponentReadinessIssue(
                        component=ComponentType.C4,
                        issue_code=ReadinessIssueCode.INCOMPLETE_PLAN_SEMANTICS,
                        message="C4 contract reference requires an explicit pinned contract_version.",
                        severity=ReadinessSeverity.BLOCKING,
                    )
                    c4_issues.append(issue)
                    blocking_issues.append(issue)
                    contract = None
                elif c4_ref.contract_id:
                    query = select(C4ContractModel).where(
                        C4ContractModel.project_id == project_id,
                        C4ContractModel.contract_id == c4_ref.contract_id,
                        C4ContractModel.version == c4_ref.contract_version,
                    )
                    contract = self.db.execute(query).scalars().first()
                else:
                    contract = None

                if not contract and not c4_issues:
                    issue = ComponentReadinessIssue(
                        component=ComponentType.C4,
                        issue_code=ReadinessIssueCode.CONTRACT_NOT_FOUND,
                        message=(
                            f"C4 policy contract '{c4_ref.contract_id}' (v{c4_ref.contract_version}) "
                            f"not found in project '{project_id}'."
                        ),
                        severity=ReadinessSeverity.BLOCKING,
                    )
                    c4_issues.append(issue)
                    blocking_issues.append(issue)
                elif contract:
                    c4_ref_id = contract.contract_id
                    c4_digest = contract.content_hash
                    c4_ref.frozen_content_hash = contract.content_hash
                    c4_ref.lifecycle_state = contract.lifecycle_state

                    if (
                        contract.lifecycle_state
                        != ContractLifecycleState.ACCEPTED.value
                    ):
                        issue = ComponentReadinessIssue(
                            component=ComponentType.C4,
                            issue_code=ReadinessIssueCode.UNACCEPTED_CONTRACT,
                            message=(
                                f"C4 policy contract '{contract.contract_id}' has lifecycle state "
                                f"'{contract.lifecycle_state}'. Must be in ACCEPTED state."
                            ),
                            severity=ReadinessSeverity.BLOCKING,
                        )
                        c4_issues.append(issue)
                        blocking_issues.append(issue)
                    else:
                        invalid_rules = []
                        for r in contract.rules_data or []:
                            try:
                                PolicyRule.model_validate(r)
                            except Exception as exc:  # noqa: BLE001
                                invalid_rules.append(str(exc))
                        if invalid_rules:
                            issue = ComponentReadinessIssue(
                                component=ComponentType.C4,
                                issue_code=ReadinessIssueCode.INVALID_POLICY_RULES,
                                message=f"C4 contract '{contract.contract_id}' contains invalid policy rules: {'; '.join(invalid_rules)}",
                                severity=ReadinessSeverity.BLOCKING,
                            )
                            c4_issues.append(issue)
                            blocking_issues.append(issue)
                        else:
                            c4_ready = True

        statuses[ComponentType.C4.value] = ComponentReadinessSummary(
            component=ComponentType.C4,
            is_ready=c4_ready,
            native_ref_id=c4_ref_id,
            frozen_digest=c4_digest,
            issues=c4_issues,
        )

        # -------------------------------------------------------------------
        # Overall Verdict Calculation
        # -------------------------------------------------------------------
        all_components_ready = c1_ready and c2_ready and c3_ready and c4_ready
        any_component_ready = c1_ready or c2_ready or c3_ready or c4_ready

        # Collect any non-blocking warnings
        for comp_summary in statuses.values():
            for iss in comp_summary.issues:
                if iss.severity in (
                    ReadinessSeverity.WARNING,
                    ReadinessSeverity.LIMITATION,
                ):
                    warnings.append(iss)

        if blocking_issues:
            is_ready = False
            verdict = ReadinessVerdict.NOT_READY
        elif all_components_ready:
            is_ready = True
            verdict = ReadinessVerdict.READY
        elif any_component_ready:
            is_ready = True  # Partial execution permitted with warnings/limitations
            verdict = ReadinessVerdict.PARTIALLY_READY
        else:
            is_ready = False
            verdict = ReadinessVerdict.NOT_READY

        return IntegrationReadinessReport(
            is_ready=is_ready,
            verdict=verdict,
            checked_at_utc=datetime.now(UTC),
            component_statuses=statuses,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    def create_run_plan(
        self,
        project: Project,
        user: User,
        data: IntegrationRunPlanCreateRequest,
    ) -> IntegrationRunPlanResponse:
        """Create and persist a frozen integration run plan with identifier mappings.

        Rejects cross-project references immediately.
        Does NOT automatically launch executions (deferred to Part 2).
        """
        project_id = project.project_id

        # 1. Immediate rejection of mismatched cross-project references
        ref_plan = ComponentReferencesPlan(
            c1=data.c1_reference,
            c2=data.c2_reference,
            c3=data.c3_reference,
            c4=data.c4_reference,
        )

        for comp_name, ref in [
            ("C1", ref_plan.c1),
            ("C2", ref_plan.c2),
            ("C3", ref_plan.c3),
            ("C4", ref_plan.c4),
        ]:
            if ref and ref.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Cross-project reference rejected: {comp_name} reference project "
                        f"'{ref.project_id}' does not match plan project '{project_id}'."
                    ),
                )

        # 2. Evaluate readiness & freeze versions/digests
        readiness = self.check_readiness(project_id, ref_plan)

        # 3. Generate stable identifiers
        plan_id = str(uuid.uuid4())
        integration_run_id = f"irun-{uuid.uuid4().hex[:12]}"

        # 4. Freeze deep execution inputs snapshot
        execution_inputs = {}
        if (
            ref_plan.c1
            and readiness.component_statuses.get(
                ComponentType.C1.value,
                ComponentReadinessSummary(component=ComponentType.C1, is_ready=False),
            ).is_ready
        ):
            c1_rec = (
                self.db.execute(
                    select(C1ProjectConfigModel).where(
                        C1ProjectConfigModel.project_id == project_id,
                        C1ProjectConfigModel.id == ref_plan.c1.config_id,
                        C1ProjectConfigModel.version == ref_plan.c1.config_version,
                    )
                )
                .scalars()
                .first()
            )
            if c1_rec:
                selected_case = None
                if ref_plan.c1.suite_id:
                    suite_rec = (
                        self.db.execute(
                            select(C1SuiteVersionModel).where(
                                C1SuiteVersionModel.project_id == project_id,
                                C1SuiteVersionModel.config_id == c1_rec.id,
                                C1SuiteVersionModel.suite_id == ref_plan.c1.suite_id,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if suite_rec and suite_rec.cases:
                        for c in suite_rec.cases:
                            c_id = (
                                c.get("case_id")
                                if isinstance(c, dict)
                                else getattr(c, "case_id", None)
                            )
                            if (
                                ref_plan.c1.case_id and c_id == ref_plan.c1.case_id
                            ) or (
                                not ref_plan.c1.case_id and len(suite_rec.cases) == 1
                            ):
                                selected_case = c
                                break

                resolved_specs, res_case_id, req_refs, case_cat = (
                    resolve_c1_expectations_from_snapshot(
                        config_expectations=c1_rec.expectations,
                        tool_constraints=c1_rec.tool_constraints,
                        suite_case=selected_case,
                    )
                )

                execution_inputs["c1"] = {
                    "config_id": c1_rec.id,
                    "version": c1_rec.version,
                    "suite_id": ref_plan.c1.suite_id,
                    "case_id": res_case_id or ref_plan.c1.case_id,
                    "category": case_cat,
                    "requirement_refs": req_refs,
                    "tools": c1_rec.tools,
                    "permitted_tools": [
                        t.get("name")
                        for t in (c1_rec.tools or [])
                        if isinstance(t, dict)
                    ],
                    "requirements": c1_rec.requirements,
                    "tool_constraints": c1_rec.tool_constraints,
                    "expectations": c1_rec.expectations,
                    "expected_tool_calls": [
                        s.model_dump(mode="json") for s in resolved_specs
                    ],
                    "agent_connection_ref": c1_rec.agent_connection_ref,
                    "context_data": {
                        "fixture_order_9821": {
                            "order_id": "ORD-9821",
                            "customer_id": "CUST-8831",
                            "status": "DELIVERED",
                            "items": {
                                "ITEM-44": {
                                    "name": "Wireless Ergonomic Mouse",
                                    "price": 35.00,
                                    "refundable": True,
                                }
                            },
                        }
                    },
                }
        if (
            ref_plan.c2
            and readiness.component_statuses.get(
                ComponentType.C2.value,
                ComponentReadinessSummary(component=ComponentType.C2, is_ready=False),
            ).is_ready
        ):
            c2_rec = (
                self.db.execute(
                    select(C2WorkflowModel).where(
                        C2WorkflowModel.project_id == project_id,
                        C2WorkflowModel.model_id == ref_plan.c2.model_id,
                        C2WorkflowModel.version == ref_plan.c2.model_version,
                    )
                )
                .scalars()
                .first()
            )
            if c2_rec:
                test_def = None
                sel_test_id = ref_plan.c2.test_id
                sel_suite_id = ref_plan.c2.suite_id

                t_query = (
                    select(C2TestCase)
                    .join(
                        C2TestSuite,
                        C2TestCase.suite_record_id == C2TestSuite.id,
                    )
                    .where(
                        C2TestCase.project_id == project_id,
                        C2TestSuite.model_id == c2_rec.model_id,
                        C2TestSuite.model_version == c2_rec.version,
                    )
                )
                if sel_suite_id:
                    t_query = t_query.where(C2TestCase.suite_id == sel_suite_id)
                if sel_test_id:
                    t_query = t_query.where(C2TestCase.test_id == sel_test_id)

                matched = self.db.execute(t_query).scalars().all()
                if matched:
                    chosen = matched[0]
                    test_def = chosen.definition
                    sel_test_id = chosen.test_id
                    sel_suite_id = chosen.suite_id

                execution_inputs["c2"] = {
                    "model_id": c2_rec.model_id,
                    "version": c2_rec.version,
                    "definition": c2_rec.definition,
                    "content_hash": c2_rec.content_hash,
                    "lifecycle_status": c2_rec.lifecycle_status,
                    "suite_id": sel_suite_id,
                    "test_id": sel_test_id,
                    "test_definition": test_def,
                }
        if (
            ref_plan.c3
            and readiness.component_statuses.get(
                ComponentType.C3.value,
                ComponentReadinessSummary(component=ComponentType.C3, is_ready=False),
            ).is_ready
        ):
            c3_rec = (
                self.db.execute(
                    select(C3SuiteModel).where(
                        C3SuiteModel.project_id == project_id,
                        C3SuiteModel.suite_digest == ref_plan.c3.suite_digest,
                    )
                )
                .scalars()
                .first()
            )
            if c3_rec:
                cases_list = (
                    [c.case_snapshot for c in c3_rec.cases] if c3_rec.cases else []
                )
                sel_case = None
                if ref_plan.c3.case_id:
                    for c_snap in cases_list:
                        if c_snap.get("case_id") == ref_plan.c3.case_id:
                            sel_case = c_snap
                            break
                    if not sel_case:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail=f"Specified C3 case_id '{ref_plan.c3.case_id}' not found in suite '{c3_rec.suite_id}'.",
                        )
                elif cases_list:
                    sel_case = cases_list[0]
                    ref_plan.c3.case_id = sel_case.get("case_id")
                execution_inputs["c3"] = {
                    "suite_id": c3_rec.suite_id,
                    "suite_digest": c3_rec.suite_digest,
                    "task_id": c3_rec.task_id,
                    "tool_id": c3_rec.tool_id,
                    "case": sel_case,
                    "selected_case": sel_case,
                    "recovery_contract": c3_rec.recovery_contract_snapshot,
                    "recovery_contract_snapshot": c3_rec.recovery_contract_snapshot,
                    "task_fixture_metadata_snapshot": c3_rec.task_fixture_metadata_snapshot,
                    "expected_entity_id": ref_plan.c3.expected_entity_id,
                }
        if (
            ref_plan.c4
            and readiness.component_statuses.get(
                ComponentType.C4.value,
                ComponentReadinessSummary(component=ComponentType.C4, is_ready=False),
            ).is_ready
        ):
            c4_rec = (
                self.db.execute(
                    select(C4ContractModel).where(
                        C4ContractModel.project_id == project_id,
                        C4ContractModel.contract_id == ref_plan.c4.contract_id,
                        C4ContractModel.version == ref_plan.c4.contract_version,
                    )
                )
                .scalars()
                .first()
            )
            if c4_rec:
                execution_inputs["c4"] = {
                    "contract_id": c4_rec.contract_id,
                    "version": c4_rec.version,
                    "lifecycle_state": c4_rec.lifecycle_state,
                    "rules": c4_rec.rules_data,
                    "rules_data": c4_rec.rules_data,
                    "content_hash": c4_rec.content_hash,
                    "referenced_artifact_versions": c4_rec.referenced_artifact_versions,
                }

        inputs_digest = canonical_json_digest(execution_inputs)

        frozen_payload = {
            "integration_run_id": integration_run_id,
            "project_id": project_id,
            "name": data.name,
            "description": data.description,
            "schema_version": "2026.1",
            "component_references": ref_plan.model_dump(mode="json"),
            "metadata": data.metadata,
            "execution_inputs_snapshot": execution_inputs,
            "execution_inputs_digest": inputs_digest,
        }
        plan_digest = canonical_json_digest(frozen_payload)

        lifecycle_status = (
            IntegrationPlanStatus.READY.value
            if readiness.is_ready
            else IntegrationPlanStatus.BLOCKED.value
        )

        # 5. Build identifier correlation mappings
        identifier_mappings: list[CorrelationMapping] = []

        if ref_plan.c1 and ref_plan.c1.config_id:
            identifier_mappings.append(
                CorrelationMapping(
                    component=ComponentType.C1,
                    native_entity_type=NativeEntityType.CONFIG,
                    native_id=ref_plan.c1.config_id,
                    context={"version": ref_plan.c1.config_version},
                )
            )
            if ref_plan.c1.suite_id:
                identifier_mappings.append(
                    CorrelationMapping(
                        component=ComponentType.C1,
                        native_entity_type=NativeEntityType.SUITE,
                        native_id=ref_plan.c1.suite_id,
                        context={"version": ref_plan.c1.suite_version},
                    )
                )

        if ref_plan.c2 and ref_plan.c2.model_id:
            identifier_mappings.append(
                CorrelationMapping(
                    component=ComponentType.C2,
                    native_entity_type=NativeEntityType.MODEL,
                    native_id=ref_plan.c2.model_id,
                    context={"version": ref_plan.c2.model_version},
                )
            )
            if ref_plan.c2.suite_id:
                identifier_mappings.append(
                    CorrelationMapping(
                        component=ComponentType.C2,
                        native_entity_type=NativeEntityType.SUITE,
                        native_id=ref_plan.c2.suite_id,
                    )
                )

        if ref_plan.c3 and ref_plan.c3.suite_id:
            identifier_mappings.append(
                CorrelationMapping(
                    component=ComponentType.C3,
                    native_entity_type=NativeEntityType.SUITE,
                    native_id=ref_plan.c3.suite_id,
                    context={"suite_digest": ref_plan.c3.suite_digest},
                )
            )

        if ref_plan.c4 and ref_plan.c4.contract_id:
            identifier_mappings.append(
                CorrelationMapping(
                    component=ComponentType.C4,
                    native_entity_type=NativeEntityType.CONTRACT,
                    native_id=ref_plan.c4.contract_id,
                    context={"version": ref_plan.c4.contract_version},
                )
            )

        # 6. Persist models
        plan_model = IntegrationRunPlanModel(
            id=plan_id,
            integration_run_id=integration_run_id,
            project_id=project_id,
            created_by_user_id=user.id,
            name=data.name,
            description=data.description,
            schema_version="2026.1",
            lifecycle_status=lifecycle_status,
            plan_digest=plan_digest,
            plan_payload=frozen_payload,
            readiness_report=readiness.model_dump(mode="json"),
            created_at_utc=datetime.now(UTC),
            updated_at_utc=datetime.now(UTC),
        )
        self.db.add(plan_model)

        # Persist identifier mappings
        for idx, mapping in enumerate(identifier_mappings):
            mapping_model = IntegrationIdentifierMappingModel(
                integration_run_id=integration_run_id,
                project_id=project_id,
                component_type=mapping.component.value,
                native_entity_type=mapping.native_entity_type.value,
                native_id=mapping.native_id,
                step_or_trial_index=idx,
                context_json=mapping.context,
                created_at_utc=datetime.now(UTC),
            )
            self.db.add(mapping_model)

        self.db.commit()
        self.db.refresh(plan_model)

        return IntegrationRunPlanResponse(
            plan_id=plan_model.id,
            integration_run_id=plan_model.integration_run_id,
            project_id=plan_model.project_id,
            name=plan_model.name,
            description=plan_model.description,
            schema_version=plan_model.schema_version,
            lifecycle_status=IntegrationPlanStatus(plan_model.lifecycle_status),
            plan_digest=plan_model.plan_digest,
            created_by_user_id=plan_model.created_by_user_id,
            created_at_utc=plan_model.created_at_utc,
            updated_at_utc=plan_model.updated_at_utc,
            component_references=ref_plan,
            identifier_mappings=identifier_mappings,
            readiness_report=readiness,
        )

    def get_run_plan(
        self,
        project: Project,
        plan_identifier: str,
    ) -> IntegrationRunPlanResponse:
        """Retrieve an integration run plan by its UUID or integration_run_id."""
        query = select(IntegrationRunPlanModel).where(
            IntegrationRunPlanModel.project_id == project.project_id,
            (
                (IntegrationRunPlanModel.id == plan_identifier)
                | (IntegrationRunPlanModel.integration_run_id == plan_identifier)
            ),
        )
        plan = self.db.execute(query).scalars().first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration run plan '{plan_identifier}' not found in project '{project.project_id}'.",
            )

        # Load mappings
        mapping_query = (
            select(IntegrationIdentifierMappingModel)
            .where(
                IntegrationIdentifierMappingModel.integration_run_id
                == plan.integration_run_id
            )
            .order_by(IntegrationIdentifierMappingModel.id)
        )
        db_mappings = self.db.execute(mapping_query).scalars().all()

        mappings = [
            CorrelationMapping(
                component=ComponentType(m.component_type),
                native_entity_type=NativeEntityType(m.native_entity_type),
                native_id=m.native_id,
                step_or_trial_index=m.step_or_trial_index,
                context=m.context_json or {},
            )
            for m in db_mappings
        ]

        refs = ComponentReferencesPlan(
            **(plan.plan_payload.get("component_references", {}))
        )
        readiness = IntegrationReadinessReport(**plan.readiness_report)

        return IntegrationRunPlanResponse(
            plan_id=plan.id,
            integration_run_id=plan.integration_run_id,
            project_id=plan.project_id,
            name=plan.name,
            description=plan.description,
            schema_version=plan.schema_version,
            lifecycle_status=IntegrationPlanStatus(plan.lifecycle_status),
            plan_digest=plan.plan_digest,
            created_by_user_id=plan.created_by_user_id,
            created_at_utc=plan.created_at_utc,
            updated_at_utc=plan.updated_at_utc,
            component_references=refs,
            identifier_mappings=mappings,
            readiness_report=readiness,
        )

    def list_run_plans(
        self,
        project: Project,
        page: int = 1,
        page_size: int = 20,
    ) -> IntegrationPlanListResponse:
        """List integration run plans for a project with pagination."""
        offset = (page - 1) * page_size

        count_query = select(func.count(IntegrationRunPlanModel.id)).where(
            IntegrationRunPlanModel.project_id == project.project_id
        )
        total = self.db.execute(count_query).scalar_one()

        plans_query = (
            select(IntegrationRunPlanModel)
            .where(IntegrationRunPlanModel.project_id == project.project_id)
            .order_by(desc(IntegrationRunPlanModel.created_at_utc))
            .offset(offset)
            .limit(page_size)
        )
        plans = self.db.execute(plans_query).scalars().all()

        items = [
            IntegrationRunPlanResponse(
                plan_id=p.id,
                integration_run_id=p.integration_run_id,
                project_id=p.project_id,
                name=p.name,
                description=p.description,
                schema_version=p.schema_version,
                lifecycle_status=IntegrationPlanStatus(p.lifecycle_status),
                plan_digest=p.plan_digest,
                created_by_user_id=p.created_by_user_id,
                created_at_utc=p.created_at_utc,
                updated_at_utc=p.updated_at_utc,
                component_references=ComponentReferencesPlan(
                    **(p.plan_payload.get("component_references", {}))
                ),
                identifier_mappings=[],
                readiness_report=IntegrationReadinessReport(**p.readiness_report),
            )
            for p in plans
        ]

        return IntegrationPlanListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
