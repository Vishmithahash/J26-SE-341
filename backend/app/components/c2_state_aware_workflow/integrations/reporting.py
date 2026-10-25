"""C2 report publishing adapter and contribution export service.

Generates versioned C2 report contributions and suite summaries. Implements the
typed publishing adapter interface. Honestly records stub status when no shared
multi-component report aggregator is registered.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.contracts.coverage import (
    DetailedObservedCoverage,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    FirstDivergenceDetail,
    RuntimeVerdict,
    ViolationDetail,
)
from app.components.c2_state_aware_workflow.contracts.report import (
    C2ReportContributionContract,
    C2SuiteReportContract,
    ExecutionProvenance,
)
from app.components.c2_state_aware_workflow.evaluator.coverage import (
    ObservedCoverageEngine,
)
from app.components.c2_state_aware_workflow.integrations.interfaces import (
    IntegrationStatus,
    UnifiedReportingInterface,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2EvaluationResult,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)


class C2ReportPublisher(UnifiedReportingInterface):
    """Typed publisher for C2 report contributions to shared QA aggregator."""

    status: IntegrationStatus = IntegrationStatus.STUB_PENDING_SHARED_SERVICE

    def __init__(self, aggregator_client: Any | None = None):
        self._aggregator_client = aggregator_client
        if aggregator_client is not None:
            self.status = IntegrationStatus.CONNECTED
        else:
            self.status = IntegrationStatus.STUB_PENDING_SHARED_SERVICE

    @property
    def is_aggregator_connected(self) -> bool:
        return self._aggregator_client is not None

    def publish(self, evaluation: Any) -> str:
        return self.publish_component_finding(evaluation)

    def publish_component_finding(self, evaluation: Any) -> str:
        """Publish C2 finding or return standalone serialized export."""
        if self._aggregator_client is not None:
            return str(self._aggregator_client.publish(evaluation))
        # No aggregator connected: record honest status and return serialized payload
        return "STUB_PENDING_SHARED_AGGREGATOR"


class C2ReportExportService:
    """Builds typed per-run and suite-level report contributions."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = C2ModelRepository(db)
        self.publisher = C2ReportPublisher()

    def build_run_report(
        self,
        project_id: str,
        evaluation_id: str,
    ) -> C2ReportContributionContract:
        """Construct a complete C2 report contribution for an individual test run."""
        eval_record = self.repo.get_evaluation_result(project_id, evaluation_id)
        if eval_record is None:
            raise ValueError(f"Evaluation '{evaluation_id}' not found.")

        # Retained evidence
        evidence_rec = self.repo.get_execution_evidence(project_id, eval_record.run_id)

        # Retrieve model
        model_rec = self.repo.get_model(
            project_id, eval_record.model_id, eval_record.model_version
        )
        if model_rec is None:
            raise ValueError(f"Pinned model '{eval_record.model_id}' not found.")
        model_def = EFSMModelDefinition(**model_rec.definition)

        # Retrieve test case to check intended execution mode
        case_rec = self.repo.get_test_case(
            project_id, eval_record.suite_id, eval_record.test_id
        )
        intended_mode = case_rec.execution_mode if case_rec else "live_agent"

        # Provenance
        if evidence_rec and evidence_rec.execution_provenance:
            prov_dict = dict(evidence_rec.execution_provenance)
            # Records from a real agent run (or derived from one) had a live LLM runner; older
            # records did not store these flags
            ran_live = bool(
                prov_dict.get("is_live_execution") or prov_dict.get("derived_from_live_execution")
            )
            default_unavailable = ["shared_intake_service", "unified_report_aggregator"]
            if not ran_live:
                default_unavailable = ["live_llm_runner", *default_unavailable]
            prov = ExecutionProvenance(
                intended_execution_mode=prov_dict.get(
                    "intended_execution_mode", intended_mode
                ),
                actual_execution_origin=prov_dict.get(
                    "actual_execution_origin", evidence_rec.execution_mode
                ),
                runner_id=prov_dict.get("runner_id", evidence_rec.runner_id),
                runner_version=prov_dict.get(
                    "runner_version", evidence_rec.runner_version
                ),
                is_live_execution=prov_dict.get("is_live_execution", False),
                observation_capabilities=prov_dict.get(
                    "observation_capabilities",
                    ["state_snapshots", "before_after_diffs", "event_logs"],
                ),
                live_capabilities_available=prov_dict.get(
                    "live_capabilities_available", ran_live
                ),
                unavailable_live_capabilities=prov_dict.get(
                    "unavailable_live_capabilities", default_unavailable
                ),
            )
        else:
            prov = ExecutionProvenance(
                intended_execution_mode=intended_mode,
                actual_execution_origin="scripted_synthetic_demonstration",
                runner_id="local_synthetic_runner_v1",
                is_live_execution=False,
                unavailable_live_capabilities=[
                    "live_llm_runner",
                    "shared_intake_service",
                    "unified_report_aggregator",
                ],
            )

        # Detailed coverage
        cov_data = eval_record.coverage or {}
        det_cov: DetailedObservedCoverage | None = None
        if "detailed_coverage" in cov_data and isinstance(
            cov_data["detailed_coverage"], dict
        ):
            try:
                det_cov = DetailedObservedCoverage(**cov_data["detailed_coverage"])
            except (ValueError, TypeError, KeyError):
                det_cov = None

        if det_cov is None:
            coverage_engine = ObservedCoverageEngine(model_def)
            det_cov = coverage_engine.compute_coverage(
                covered_transitions=set(cov_data.get("covered_transitions", [])),
                guard_true_outcomes=set(cov_data.get("guard_true_outcomes", [])),
                guard_false_outcomes=set(cov_data.get("guard_false_outcomes", [])),
                guard_unknown_observations=set(
                    cov_data.get("guard_unknown_observations", [])
                ),
                satisfied_effects=set(cov_data.get("satisfied_effects", [])),
                violated_effects=set(cov_data.get("violated_effects", [])),
                unknown_effects=set(cov_data.get("unknown_effects", [])),
                completed_path_history=cov_data.get("path_history", []),
                is_terminal_accepting=eval_record.verdict
                in (
                    RuntimeVerdict.PASS.value,
                    RuntimeVerdict.EXPECTED_REJECTION_PASS.value,
                ),
            )
        det_cov = det_cov.model_copy(
            update={"model_content_hash": eval_record.model_content_hash}
        )

        verdict_enum = RuntimeVerdict(eval_record.verdict)
        is_readiness = verdict_enum in (
            RuntimeVerdict.MODEL_NOT_READY,
            RuntimeVerdict.TEST_NOT_READY,
        )

        first_div = (
            FirstDivergenceDetail(**eval_record.first_divergence)
            if eval_record.first_divergence
            else None
        )

        readiness_limits: list[str] = []
        if is_readiness:
            readiness_limits.extend(eval_record.reasons)

        obs_limits: list[str] = []
        if not evidence_rec:
            obs_limits.append("Original execution evidence record not retained.")

        digest = eval_record.evidence_digest or (
            evidence_rec.evidence_digest if evidence_rec else "digest_not_retained"
        )

        return C2ReportContributionContract(
            component="C2_STATE_AWARE_WORKFLOW",
            contract_version="2026.1",
            project_id=eval_record.project_id,
            suite_id=eval_record.suite_id,
            test_id=eval_record.test_id,
            run_id=eval_record.run_id,
            evaluation_id=eval_record.id,
            model_id=eval_record.model_id,
            model_version=eval_record.model_version,
            model_content_hash=eval_record.model_content_hash,
            fixture_version="2026.1",
            runner_version=prov.runner_version,
            evaluator_version=eval_record.evaluator_version,
            execution_provenance=prov,
            verdict=verdict_enum,
            verdict_category=(
                "READINESS_REJECTION" if is_readiness else "EVALUATION_OUTCOME"
            ),
            reason_codes=eval_record.reasons,
            expected_states=eval_record.expected_states,
            observed_states=eval_record.observed_states,
            accepted_alternatives=first_div.expected_alternatives if first_div else [],
            violated_rules=[ViolationDetail(**v) for v in eval_record.violations],
            first_divergence=first_div,
            divergence_localisation_uncertainty=(
                "Evidence contains observation limitations or gaps; earliest divergence point uncertain."
                if obs_limits
                else None
            ),
            evidence_digest=digest,
            evidence_references=eval_record.evidence_references,
            observed_coverage=det_cov,
            readiness_limitations=readiness_limits,
            observation_limitations=obs_limits,
            evaluator_timing_ms=eval_record.evaluator_timing_ms,
            evaluated_at=eval_record.created_at,
            published_to_shared_aggregator=False,
            publishing_status="STUB_PENDING_SHARED_AGGREGATOR",
        )

    def build_suite_report(
        self,
        project_id: str,
        suite_id: str,
    ) -> C2SuiteReportContract:
        """Construct aggregated suite-level C2 report."""
        suite_rec = self.repo.get_test_suite(project_id, suite_id)
        if suite_rec is None:
            raise ValueError(f"Suite '{suite_id}' not found.")

        model_rec = self.repo.get_model(
            project_id, suite_rec.model_id, suite_rec.model_version
        )
        if model_rec is None:
            raise ValueError(f"Pinned model '{suite_rec.model_id}' not found.")
        model_def = EFSMModelDefinition(**model_rec.definition)

        eval_records = self.repo.list_evaluation_results(project_id, suite_id=suite_id)

        # Deduplicate to latest evaluation attempt per run_id
        latest_evals_by_run: dict[str, C2EvaluationResult] = {}
        for er in eval_records:
            if (
                er.run_id not in latest_evals_by_run
                or er.evaluation_attempt
                > latest_evals_by_run[er.run_id].evaluation_attempt
            ):
                latest_evals_by_run[er.run_id] = er
        selected_evals = list(latest_evals_by_run.values())

        verdict_counts: dict[str, int] = {v.value: 0 for v in RuntimeVerdict}
        readiness_rejections: dict[str, int] = {
            RuntimeVerdict.MODEL_NOT_READY.value: 0,
            RuntimeVerdict.TEST_NOT_READY.value: 0,
        }
        scored_outcomes: dict[str, int] = {
            RuntimeVerdict.PASS.value: 0,
            RuntimeVerdict.EXPECTED_REJECTION_PASS.value: 0,
            RuntimeVerdict.FAIL.value: 0,
            RuntimeVerdict.INCONCLUSIVE.value: 0,
        }

        run_reports: list[C2ReportContributionContract] = []
        run_coverages: list[DetailedObservedCoverage] = []

        for er in selected_evals:
            v_val = er.verdict
            verdict_counts[v_val] = verdict_counts.get(v_val, 0) + 1
            if v_val in readiness_rejections:
                readiness_rejections[v_val] += 1
            if v_val in scored_outcomes:
                scored_outcomes[v_val] += 1

            run_rep = self.build_run_report(project_id, er.id)
            run_reports.append(run_rep)
            run_coverages.append(run_rep.observed_coverage)

        # Aggregate coverage using unique target sets
        agg_cov = ObservedCoverageEngine.aggregate_suite_coverage(
            model=model_def,
            run_coverages=run_coverages,
        )
        agg_cov = agg_cov.model_copy(
            update={"model_content_hash": suite_rec.model_content_hash}
        )

        return C2SuiteReportContract(
            component="C2_STATE_AWARE_WORKFLOW",
            contract_version="2026.1",
            project_id=project_id,
            suite_id=suite_id,
            model_id=suite_rec.model_id,
            model_version=suite_rec.model_version,
            model_content_hash=suite_rec.model_content_hash,
            total_cases=suite_rec.total_cases,
            evaluated_cases=len(eval_records),
            verdict_counts=verdict_counts,
            readiness_rejection_counts=readiness_rejections,
            scored_agent_outcomes=scored_outcomes,
            aggregate_observed_coverage=agg_cov,
            case_reports=run_reports,
            published_to_shared_aggregator=False,
            publishing_status="STUB_PENDING_SHARED_AGGREGATOR",
            generated_at=datetime.now(UTC),
        )
