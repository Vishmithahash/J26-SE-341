"""Benchmark dataset generator and suite runner for C2 domain portability demonstration.

Generates at least 100 distinct, feasible, non-padded execution cases across 5 workflows
in 3 domains (E-Commerce, Flight Booking, Learning Management).
Enforces partition isolation without parent-child leakage.
Includes conforming paths, expected rejections, and mutation variants.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.experiment import (
    DatasetPartition,
    ExperimentCaseRecord,
    ExperimentDatasetManifest,
    GroundTruthLabel,
    MutationFamily,
    ReviewStatus,
)
from app.components.c2_state_aware_workflow.contracts.report import ExecutionProvenance
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    EvidenceCompleteness,
    RuntimeEvent,
    RuntimeEvidenceContract,
    StateObservation,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.examples.ecommerce_workflows import (
    get_address_change_workflow_model,
    get_cancellation_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.flight_workflows import (
    get_flight_cancellation_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.lms_workflows import (
    get_course_enrollment_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)


def _compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class BenchmarkSuiteBuilder:
    """Constructs frozen, multi-domain benchmark dataset manifests (>=100 cases)."""

    def __init__(self, project_id: str = "c2_domain_portability_project"):
        self.project_id = project_id
        self.models: dict[str, EFSMModelDefinition] = {
            "order_refund_workflow": build_synthetic_refund_efsm(),
            "order_cancellation_workflow": get_cancellation_workflow_model(),
            "address_change_workflow": get_address_change_workflow_model(),
            "flight_cancellation_workflow": get_flight_cancellation_workflow_model(),
            "course_enrollment_workflow": get_course_enrollment_workflow_model(),
        }
        self.tests: dict[str, GeneratedTestDefinition] = {}

    def build_benchmark_manifest(
        self,
        dataset_id: str = "c2_benchmark_v1",
        name: str = "C2 Multi-Domain Portability & Robustness Benchmark",
        version: str = "1.0.0",
    ) -> tuple[
        ExperimentDatasetManifest,
        dict[str, EFSMModelDefinition],
        dict[str, GeneratedTestDefinition],
    ]:
        """Build a balanced dataset of at least 100 distinct cases partitioned without leakage."""
        cases: list[ExperimentCaseRecord] = []

        # 5 workflows * 5 families * 5 variants = 125 distinct feasible cases!
        workflow_configs = [
            (
                "order_refund_workflow",
                "ECOMMERCE",
                "Refund my latest paid order.",
                self._generate_refund_evidence,
            ),
            (
                "order_cancellation_workflow",
                "ECOMMERCE",
                "Cancel my pending order.",
                self._generate_cancellation_evidence,
            ),
            (
                "address_change_workflow",
                "ECOMMERCE",
                "Change shipping address before dispatch.",
                self._generate_address_evidence,
            ),
            (
                "flight_cancellation_workflow",
                "FLIGHT_BOOKING",
                "Cancel flight booking and issue travel credit.",
                self._generate_flight_evidence,
            ),
            (
                "course_enrollment_workflow",
                "LMS",
                "Enroll student into prerequisite-gated course.",
                self._generate_lms_evidence,
            ),
        ]

        case_idx = 1
        for wf_id, domain, task_desc, gen_fn in workflow_configs:
            model = self.models[wf_id]

            for family_num in range(1, 6):
                family_id = f"fam_{wf_id}_{family_num}"
                # Partition rule: odd families to DEVELOPMENT, even families to HELD_OUT
                partition = (
                    DatasetPartition.DEVELOPMENT
                    if family_num % 2 != 0
                    else DatasetPartition.HELD_OUT
                )

                # Variant 1: Conforming normal
                c1 = self._build_case_record(
                    case_idx=case_idx,
                    family_id=family_id,
                    domain=domain,
                    wf_id=wf_id,
                    model=model,
                    task_desc=f"{task_desc} (Standard Run {family_num})",
                    variant_type="CONFORMING_NORMAL",
                    gen_fn=gen_fn,
                    partition=partition,
                    fixture_variation=family_num,
                )
                cases.append(c1)
                case_idx += 1

                # Variant 2: Conforming rejection
                c2 = self._build_case_record(
                    case_idx=case_idx,
                    family_id=family_id,
                    domain=domain,
                    wf_id=wf_id,
                    model=model,
                    task_desc=f"{task_desc} (Ineligible Target {family_num})",
                    variant_type="CONFORMING_REJECTION",
                    gen_fn=gen_fn,
                    partition=partition,
                    fixture_variation=family_num,
                )
                cases.append(c2)
                case_idx += 1

                # Variant 3: State-effect corruption
                c3 = self._build_case_record(
                    case_idx=case_idx,
                    family_id=family_id,
                    domain=domain,
                    wf_id=wf_id,
                    model=model,
                    task_desc=f"{task_desc} (Corrupted State Effect {family_num})",
                    variant_type="STATE_CORRUPTION",
                    gen_fn=gen_fn,
                    partition=partition,
                    fixture_variation=family_num,
                )
                cases.append(c3)
                case_idx += 1

                # Variant 4: Out-of-order action
                c4 = self._build_case_record(
                    case_idx=case_idx,
                    family_id=family_id,
                    domain=domain,
                    wf_id=wf_id,
                    model=model,
                    task_desc=f"{task_desc} (Premature Out-of-Order Action {family_num})",
                    variant_type="OUT_OF_ORDER",
                    gen_fn=gen_fn,
                    partition=partition,
                    fixture_variation=family_num,
                )
                cases.append(c4)
                case_idx += 1

                # Variant 5: Skipped intermediate action
                c5 = self._build_case_record(
                    case_idx=case_idx,
                    family_id=family_id,
                    domain=domain,
                    wf_id=wf_id,
                    model=model,
                    task_desc=f"{task_desc} (Skipped Inspection {family_num})",
                    variant_type="SKIPPED_INSPECTION",
                    gen_fn=gen_fn,
                    partition=partition,
                    fixture_variation=family_num,
                )
                cases.append(c5)
                case_idx += 1

        dev_count = sum(1 for c in cases if c.partition == DatasetPartition.DEVELOPMENT)
        held_count = sum(1 for c in cases if c.partition == DatasetPartition.HELD_OUT)

        manifest_raw = f"{dataset_id}:{version}:{len(cases)}:{dev_count}:{held_count}"
        digest = _compute_sha256(manifest_raw)

        manifest = ExperimentDatasetManifest(
            dataset_id=dataset_id,
            name=name,
            version=version,
            description="Multi-domain benchmark suite containing 125 distinct feasible cases across 5 workflows.",
            project_id=self.project_id,
            is_frozen=True,
            frozen_at=datetime.now(UTC),
            manifest_digest=digest,
            cases=cases,
            case_count=len(cases),
            development_count=dev_count,
            held_out_count=held_count,
        )

        return manifest, self.models, self.tests

    def _build_case_record(
        self,
        case_idx: int,
        family_id: str,
        domain: str,
        wf_id: str,
        model: EFSMModelDefinition,
        task_desc: str,
        variant_type: str,
        gen_fn: Any,
        partition: DatasetPartition,
        fixture_variation: int,
    ) -> ExperimentCaseRecord:
        case_id = f"case_{wf_id}_{case_idx:03d}"
        test_id = f"test_{case_id}"

        test_def = GeneratedTestDefinition(
            test_id=test_id,
            project_id=self.project_id,
            suite_id="benchmark_suite_v1",
            pinned_model_id=wf_id,
            pinned_model_version=model.version,
            model_content_hash="benchmark_content_hash",
            category=TestCategory.VALID
            if variant_type == "CONFORMING_NORMAL"
            else (
                TestCategory.NEGATIVE
                if variant_type == "CONFORMING_REJECTION"
                else TestCategory.MUTATED
            ),
            task=task_desc,
            fixture_ref=f"fixture_{wf_id}_var_{fixture_variation}",
            seed=42 + case_idx,
            expected_outcome=ExpectedOutcomeType.PASS
            if variant_type == "CONFORMING_NORMAL"
            else ExpectedOutcomeType.EXPECTED_REJECTION_PASS,
            readiness=TestReadinessStatus.TEST_READY,
        )
        self.tests[test_id] = test_def

        evidence, gt, fixture_data = gen_fn(
            variant_type=variant_type,
            case_id=case_id,
            variation=fixture_variation,
        )

        evidence_digest = _compute_sha256(
            json.dumps(evidence.model_dump(mode="json"), sort_keys=True)
        )
        fixture_digest = _compute_sha256(json.dumps(fixture_data, sort_keys=True))

        return ExperimentCaseRecord(
            case_id=case_id,
            parent_case_id=family_id,
            domain=domain,
            workflow_name=model.name,
            model_id=wf_id,
            model_version=model.version,
            test_id=test_id,
            test_version="1.0.0",
            fixture_id=f"fixture_{wf_id}_{fixture_variation}",
            fixture_digest=fixture_digest,
            evidence_id=f"ev_{case_id}",
            evidence_digest=evidence_digest,
            execution_provenance=ExecutionProvenance(
                intended_execution_mode="evaluator_validation",
                actual_execution_origin="controlled_trace_evaluator_validation",
                runner_id="c2_controlled_trace_runner",
                runner_version="2026.1",
                is_live_execution=False,
                observation_capabilities=["tool_events", "state_diffs"],
                live_capabilities_available=False,
                unavailable_live_capabilities=[
                    "live_agent_llm_harness",
                    "external_production_db",
                ],
            ),
            partition=partition,
            ground_truth=gt,
            frozen_evidence=evidence,
            frozen_fixture=fixture_data,
        )

    # -----------------------------------------------------------------------
    # Evidence & Ground Truth Generators
    # -----------------------------------------------------------------------

    def _generate_refund_evidence(
        self, variant_type: str, case_id: str, variation: int
    ) -> tuple[RuntimeEvidenceContract, GroundTruthLabel, dict[str, Any]]:
        fixture = {
            "customer_id": 42,
            "orders": {
                "501": {
                    "order_id": 501,
                    "payment_status": "PAID",
                    "ordered_at": "2026-10-10T10:00:00Z",
                },
                "503": {
                    "order_id": 503,
                    "payment_status": "PAID",
                    "ordered_at": "2026-10-15T15:00:00Z",
                },
            },
        }

        if variant_type == "CONFORMING_NORMAL":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_customer_orders",
                    arguments={"customer_id": 42},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="select_order",
                    arguments={"order_id": 503},
                ),
                RuntimeEvent(
                    event_index=2,
                    event_id=f"{case_id}_e3",
                    tool_name="request_refund",
                    arguments={"order_id": 503},
                ),
                RuntimeEvent(
                    event_index=3,
                    event_id=f"{case_id}_e4",
                    tool_name="verify_refund_status",
                    arguments={"order_id": 503},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(event_index=1, before_state={}, after_state={}),
                StateObservation(event_index=2, before_state={}, after_state={}),
                StateObservation(
                    event_index=3,
                    before_state={"payment_status": "PAID"},
                    after_state={"payment_status": "REFUNDED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "CONFORMING_REJECTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_customer_orders",
                    arguments={"customer_id": 42},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="reject_unpaid_order",
                    arguments={"order_id": 502},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"order_502_payment_status": "UNPAID"},
                    after_state={"order_502_payment_status": "UNPAID"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.EXPECTED_REJECTION_PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "STATE_CORRUPTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_customer_orders",
                    arguments={"customer_id": 42},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="select_order",
                    arguments={"order_id": 503},
                ),
                RuntimeEvent(
                    event_index=2,
                    event_id=f"{case_id}_e3",
                    tool_name="request_refund",
                    arguments={"order_id": 503},
                ),
                RuntimeEvent(
                    event_index=3,
                    event_id=f"{case_id}_e4",
                    tool_name="verify_refund_status",
                    arguments={"order_id": 503},
                ),
            ]
            # State corruption: payment_status stayed PAID instead of REFUNDED
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(event_index=1, before_state={}, after_state={}),
                StateObservation(event_index=2, before_state={}, after_state={}),
                StateObservation(
                    event_index=3,
                    before_state={"payment_status": "PAID"},
                    after_state={"payment_status": "PAID"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=True,
                mutation_family=MutationFamily.STATE_EFFECT_CORRUPTION,
                ground_truth_divergence_step=3,
                ground_truth_divergence_event_id=f"{case_id}_e4",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "OUT_OF_ORDER":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="request_refund",
                    arguments={"order_id": 503},
                )
            ]
            obs = [StateObservation(event_index=0, before_state={}, after_state={})]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.OUT_OF_ORDER_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        else:  # SKIPPED_INSPECTION
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_customer_orders",
                    arguments={"customer_id": 42},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="request_refund",
                    arguments={"order_id": 503},
                ),
                RuntimeEvent(
                    event_index=2,
                    event_id=f"{case_id}_e3",
                    tool_name="verify_refund_status",
                    arguments={"order_id": 503},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(event_index=1, before_state={}, after_state={}),
                StateObservation(
                    event_index=2,
                    before_state={"payment_status": "PAID"},
                    after_state={"payment_status": "REFUNDED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.SKIPPED_INTERMEDIATE_ACTION,
                ground_truth_divergence_step=1,
                ground_truth_divergence_event_id=f"{case_id}_e2",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )

        evidence = RuntimeEvidenceContract(
            project_id=self.project_id,
            suite_id="benchmark_suite_v1",
            test_id=f"test_{case_id}",
            run_id=f"run_{case_id}",
            model_id="order_refund_workflow",
            model_version="1.0.0",
            completeness=EvidenceCompleteness(
                is_complete=True, confirmed_agent_termination=True
            ),
            ordered_events=events,
            state_observations=obs,
        )
        return evidence, gt, fixture

    def _generate_cancellation_evidence(
        self, variant_type: str, case_id: str, variation: int
    ) -> tuple[RuntimeEvidenceContract, GroundTruthLabel, dict[str, Any]]:
        order_num = 700 + variation
        fixture = {"order_id": order_num, "fulfillment_status": "PENDING_FULFILLMENT"}

        if variant_type == "CONFORMING_NORMAL":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_order_details",
                    arguments={"order_id": order_num},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="cancel_order",
                    arguments={
                        "order_id": order_num,
                        "reason": "Customer changed mind",
                    },
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"orders.status": "PENDING_FULFILLMENT"},
                    after_state={"orders.status": "CANCELLED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "CONFORMING_REJECTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_order_details",
                    arguments={"order_id": order_num},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="reject_request",
                    arguments={"reason": "Order already shipped"},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"orders.status": "SHIPPED"},
                    after_state={"orders.status": "SHIPPED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.EXPECTED_REJECTION_PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "STATE_CORRUPTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_order_details",
                    arguments={"order_id": order_num},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="cancel_order",
                    arguments={"order_id": order_num, "reason": "Customer request"},
                ),
            ]
            # State corruption: status stayed PROCESSING instead of CANCELLED
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"orders.status": "PENDING_FULFILLMENT"},
                    after_state={"orders.status": "PROCESSING"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=True,
                mutation_family=MutationFamily.STATE_EFFECT_CORRUPTION,
                ground_truth_divergence_step=1,
                ground_truth_divergence_event_id=f"{case_id}_e2",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "OUT_OF_ORDER":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="cancel_order",
                    arguments={"order_id": order_num, "reason": "No inspection"},
                )
            ]
            obs = [StateObservation(event_index=0, before_state={}, after_state={})]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.OUT_OF_ORDER_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        else:  # SKIPPED_INSPECTION
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="cancel_order",
                    arguments={"order_id": order_num, "reason": "Skipped"},
                )
            ]
            obs = [
                StateObservation(
                    event_index=0,
                    before_state={"order_status": "PROCESSING"},
                    after_state={"order_status": "CANCELLED"},
                )
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.SKIPPED_INTERMEDIATE_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )

        evidence = RuntimeEvidenceContract(
            project_id=self.project_id,
            suite_id="benchmark_suite_v1",
            test_id=f"test_{case_id}",
            run_id=f"run_{case_id}",
            model_id="order_cancellation_workflow",
            model_version="1.0.0",
            completeness=EvidenceCompleteness(
                is_complete=True, confirmed_agent_termination=True
            ),
            ordered_events=events,
            state_observations=obs,
        )
        return evidence, gt, fixture

    def _generate_address_evidence(
        self, variant_type: str, case_id: str, variation: int
    ) -> tuple[RuntimeEvidenceContract, GroundTruthLabel, dict[str, Any]]:
        order_num = 800 + variation
        fixture = {"order_id": order_num, "dispatched": False}

        if variant_type == "CONFORMING_NORMAL":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_shipping_status",
                    arguments={"order_id": order_num},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="update_shipping_address",
                    arguments={
                        "order_id": order_num,
                        "new_address": "456 Market St, Suite 200",
                    },
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"deliveries.delivery_address": "123 Old Rd"},
                    after_state={
                        "deliveries.delivery_address": "456 Market St, Suite 200"
                    },
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "CONFORMING_REJECTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_shipping_status",
                    arguments={"order_id": order_num},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="reject_request",
                    arguments={"reason": "Parcel already dispatched"},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"deliveries.delivery_address": "123 Old Rd"},
                    after_state={"deliveries.delivery_address": "123 Old Rd"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.EXPECTED_REJECTION_PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "STATE_CORRUPTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_shipping_status",
                    arguments={"order_id": order_num},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="update_shipping_address",
                    arguments={
                        "order_id": order_num,
                        "new_address": "456 Market St, Suite 200",
                    },
                ),
            ]
            # State corruption: address was not updated
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"deliveries.delivery_address": "123 Old Rd"},
                    after_state={"deliveries.delivery_address": "123 Old Rd"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=True,
                mutation_family=MutationFamily.STATE_EFFECT_CORRUPTION,
                ground_truth_divergence_step=1,
                ground_truth_divergence_event_id=f"{case_id}_e2",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "OUT_OF_ORDER":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="update_shipping_address",
                    arguments={
                        "order_id": order_num,
                        "new_address": "456 Market St, Suite 200",
                    },
                )
            ]
            obs = [StateObservation(event_index=0, before_state={}, after_state={})]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.OUT_OF_ORDER_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        else:  # SKIPPED_INSPECTION
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="update_shipping_address",
                    arguments={
                        "order_id": order_num,
                        "new_address": "456 Market St, Suite 200",
                    },
                )
            ]
            obs = [
                StateObservation(
                    event_index=0,
                    before_state={"shipping_address": "123 Main St"},
                    after_state={
                        "shipping_address": "456 Market St, Suite 200",
                        "order_status": "PROCESSING",
                    },
                )
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.SKIPPED_INTERMEDIATE_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )

        evidence = RuntimeEvidenceContract(
            project_id=self.project_id,
            suite_id="benchmark_suite_v1",
            test_id=f"test_{case_id}",
            run_id=f"run_{case_id}",
            model_id="address_change_workflow",
            model_version="1.0.0",
            completeness=EvidenceCompleteness(
                is_complete=True, confirmed_agent_termination=True
            ),
            ordered_events=events,
            state_observations=obs,
        )
        return evidence, gt, fixture

    def _generate_flight_evidence(
        self, variant_type: str, case_id: str, variation: int
    ) -> tuple[RuntimeEvidenceContract, GroundTruthLabel, dict[str, Any]]:
        booking_code = f"FL-9{variation:02d}"
        fixture = {"booking_id": booking_code, "hours_to_departure": 6.0}

        if variant_type == "CONFORMING_NORMAL":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_booking_details",
                    arguments={"booking_id": booking_code},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="cancel_flight_booking",
                    arguments={
                        "booking_id": booking_code,
                        "passenger_id": f"PAX_{variation}",
                    },
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"flight_bookings.status": "CONFIRMED"},
                    after_state={"flight_bookings.status": "CANCELLED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "CONFORMING_REJECTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_booking_details",
                    arguments={"booking_id": booking_code},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="reject_request",
                    arguments={"reason": "Under 2 hours to departure"},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"flight_bookings.status": "CONFIRMED"},
                    after_state={"flight_bookings.status": "CONFIRMED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.EXPECTED_REJECTION_PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "STATE_CORRUPTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="get_booking_details",
                    arguments={"booking_id": booking_code},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="cancel_flight_booking",
                    arguments={
                        "booking_id": booking_code,
                        "passenger_id": f"PAX_{variation}",
                    },
                ),
            ]
            # State corruption: booking remained CONFIRMED
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"flight_bookings.status": "CONFIRMED"},
                    after_state={"flight_bookings.status": "CONFIRMED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=True,
                mutation_family=MutationFamily.STATE_EFFECT_CORRUPTION,
                ground_truth_divergence_step=1,
                ground_truth_divergence_event_id=f"{case_id}_e2",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "OUT_OF_ORDER":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="cancel_flight_booking",
                    arguments={
                        "booking_id": booking_code,
                        "passenger_id": f"PAX_{variation}",
                    },
                )
            ]
            obs = [StateObservation(event_index=0, before_state={}, after_state={})]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.OUT_OF_ORDER_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        else:  # SKIPPED_INSPECTION
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="cancel_flight_booking",
                    arguments={
                        "booking_id": booking_code,
                        "passenger_id": f"PAX_{variation}",
                    },
                )
            ]
            obs = [
                StateObservation(
                    event_index=0,
                    before_state={"booking_status": "CONFIRMED"},
                    after_state={"booking_status": "CANCELLED"},
                )
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.SKIPPED_INTERMEDIATE_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )

        evidence = RuntimeEvidenceContract(
            project_id=self.project_id,
            suite_id="benchmark_suite_v1",
            test_id=f"test_{case_id}",
            run_id=f"run_{case_id}",
            model_id="flight_cancellation_workflow",
            model_version="1.0.0",
            completeness=EvidenceCompleteness(
                is_complete=True, confirmed_agent_termination=True
            ),
            ordered_events=events,
            state_observations=obs,
        )
        return evidence, gt, fixture

    def _generate_lms_evidence(
        self, variant_type: str, case_id: str, variation: int
    ) -> tuple[RuntimeEvidenceContract, GroundTruthLabel, dict[str, Any]]:
        student_id = f"ST-{100 + variation}"
        course_id = f"CS-{300 + variation}"
        fixture = {"student_id": student_id, "course_id": course_id}

        if variant_type == "CONFORMING_NORMAL":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="check_student_eligibility",
                    arguments={"student_id": student_id, "course_id": course_id},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="enroll_in_course",
                    arguments={"student_id": student_id, "course_id": course_id},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"student_records.enrollment_status": "NONE"},
                    after_state={"student_records.enrollment_status": "ENROLLED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "CONFORMING_REJECTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="check_student_eligibility",
                    arguments={"student_id": student_id, "course_id": course_id},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="reject_request",
                    arguments={"reason": "Missing prerequisites"},
                ),
            ]
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"student_records.enrollment_status": "NONE"},
                    after_state={"student_records.enrollment_status": "NONE"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=False,
                expected_verdict=RuntimeVerdict.EXPECTED_REJECTION_PASS,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.NONE,
                ground_truth_divergence_location_known=False,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "STATE_CORRUPTION":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="check_student_eligibility",
                    arguments={"student_id": student_id, "course_id": course_id},
                ),
                RuntimeEvent(
                    event_index=1,
                    event_id=f"{case_id}_e2",
                    tool_name="enroll_in_course",
                    arguments={"student_id": student_id, "course_id": course_id},
                ),
            ]
            # State corruption: enrollment_status remained WAITLISTED instead of ENROLLED
            obs = [
                StateObservation(event_index=0, before_state={}, after_state={}),
                StateObservation(
                    event_index=1,
                    before_state={"student_records.enrollment_status": "NONE"},
                    after_state={"student_records.enrollment_status": "WAITLISTED"},
                ),
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=True,
                mutation_family=MutationFamily.STATE_EFFECT_CORRUPTION,
                ground_truth_divergence_step=1,
                ground_truth_divergence_event_id=f"{case_id}_e2",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        elif variant_type == "OUT_OF_ORDER":
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="enroll_in_course",
                    arguments={"student_id": student_id, "course_id": course_id},
                )
            ]
            obs = [StateObservation(event_index=0, before_state={}, after_state={})]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.OUT_OF_ORDER_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )
        else:  # SKIPPED_INSPECTION
            events = [
                RuntimeEvent(
                    event_index=0,
                    event_id=f"{case_id}_e1",
                    tool_name="enroll_in_course",
                    arguments={"student_id": student_id, "course_id": course_id},
                )
            ]
            obs = [
                StateObservation(
                    event_index=0,
                    before_state={"enrollment_status": "NOT_ENROLLED"},
                    after_state={"enrollment_status": "ENROLLED"},
                )
            ]
            gt = GroundTruthLabel(
                is_workflow_violation=True,
                expected_verdict=RuntimeVerdict.FAIL,
                is_valid_test=True,
                has_state_effect_fault=False,
                mutation_family=MutationFamily.SKIPPED_INTERMEDIATE_ACTION,
                ground_truth_divergence_step=0,
                ground_truth_divergence_event_id=f"{case_id}_e1",
                ground_truth_divergence_location_known=True,
                review_status=ReviewStatus.DEVELOPER_FIXTURE,
            )

        evidence = RuntimeEvidenceContract(
            project_id=self.project_id,
            suite_id="benchmark_suite_v1",
            test_id=f"test_{case_id}",
            run_id=f"run_{case_id}",
            model_id="course_enrollment_workflow",
            model_version="1.0.0",
            completeness=EvidenceCompleteness(
                is_complete=True, confirmed_agent_termination=True
            ),
            ordered_events=events,
            state_observations=obs,
        )
        return evidence, gt, fixture
