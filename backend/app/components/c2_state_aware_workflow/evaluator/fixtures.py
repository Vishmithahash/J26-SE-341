"""Scripted demonstration agent and controlled trace fixtures for C2 evaluation.

1. ScriptedDemonstrationAgent:
   - Clearly labelled: [SYNTHETIC_OFFLINE_DEMONSTRATION].
   - Operates against the resettable SUT using only the agent-safe task payload.
   - Does NOT receive reference paths, assertions, expected outcomes, or mutation labels.

2. ControlledTraceFixtures:
   - Clearly labelled as synthetic evaluator trace fixtures (NOT independently observed live runs).
   - Generates edge-case traces that cannot naturally occur via the live SUT:
     missing effects, protected state mutations, truncated traces, and broken correlations.
"""

import copy

from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    EvidenceCompleteness,
    RuntimeEvent,
    RuntimeEvidenceContract,
    StateObservation,
)
from app.components.c2_state_aware_workflow.evaluator.observer import (
    IndependentStateObserver,
)
from app.components.c2_state_aware_workflow.evaluator.sut import SyntheticRefundSUT


class ScriptedDemonstrationAgent:
    """Clearly labelled synthetic demonstration agent for offline C2 validation.

    NOTE: This is NOT a live LLM or NexaCart integration. It is a deterministic
    demonstrator used to verify independent state observation, trace normalization,
    trace-to-EFSM alignment, and verdict calculation.
    """

    def __init__(self, sut: SyntheticRefundSUT, observer: IndependentStateObserver):
        self.sut = sut
        self.observer = observer

    def run_happy_path(
        self,
        project_id: str,
        test_id: str,
        run_id: str,
        model_id: str,
        model_version: str,
        customer_id: int = 42,
        target_order_id: int = 503,
    ) -> RuntimeEvidenceContract:
        """Run standard valid refund workflow: get_orders -> select_order -> request_refund -> verify_refund."""
        self.sut.reset()
        idx = 0

        # Step 1: get_customer_orders
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="get_customer_orders",
            tool_callable=self.sut.get_customer_orders,
            arguments={"customer_id": customer_id},
        )
        idx += 1

        # Step 2: select_order
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="select_order",
            tool_callable=self.sut.select_order,
            arguments={"customer_id": customer_id, "order_id": target_order_id},
        )
        idx += 1

        # Step 3: request_refund
        refund_res = self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="request_refund",
            tool_callable=self.sut.request_refund,
            arguments={
                "customer_id": customer_id,
                "order_id": target_order_id,
                "reason": "damaged",
            },
        )
        idx += 1
        refund_id = refund_res.get(
            "refund_id", f"ref_{customer_id}_{target_order_id}_1"
        )

        # Step 4: verify_refund_status
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="verify_refund_status",
            tool_callable=self.sut.verify_refund_status,
            arguments={"refund_id": refund_id},
        )

        return RuntimeEvidenceContract(
            project_id=project_id,
            run_id=run_id,
            test_id=test_id,
            model_id=model_id,
            model_version=model_version,
            ordered_events=copy.deepcopy(self.observer.events),
            state_observations=copy.deepcopy(self.observer.observations),
            completeness=EvidenceCompleteness(
                has_all_events=True,
                has_state_snapshots=True,
                has_db_diffs=True,
                is_complete=True,
                is_truncated=False,
                confirmed_agent_termination=True,
                termination_reason="AGENT_COMPLETED_SUCCESSFULLY",
            ),
            execution_mode="synthetic_demonstration_agent",
            collector_provenance={
                "agent_type": "ScriptedDemonstrationAgent",
                "scenario": "happy_path",
            },
        )

    def run_inspection_alternative(
        self,
        project_id: str,
        test_id: str,
        run_id: str,
        model_id: str,
        model_version: str,
        customer_id: int = 42,
        target_order_id: int = 503,
    ) -> RuntimeEvidenceContract:
        """Run permitted alternative workflow with optional inspection step."""
        self.sut.reset()
        idx = 0

        # Step 1: get_customer_orders
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="get_customer_orders",
            tool_callable=self.sut.get_customer_orders,
            arguments={"customer_id": customer_id},
        )
        idx += 1

        # Step 2: select_order
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="select_order",
            tool_callable=self.sut.select_order,
            arguments={"customer_id": customer_id, "order_id": target_order_id},
        )
        idx += 1

        # Step 3: get_order_details (permitted optional alternative)
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="get_order_details",
            tool_callable=self.sut.get_order_details,
            arguments={"order_id": target_order_id},
        )
        idx += 1

        # Step 4: request_refund
        refund_res = self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="request_refund",
            tool_callable=self.sut.request_refund,
            arguments={
                "customer_id": customer_id,
                "order_id": target_order_id,
                "reason": "unwanted",
            },
        )
        idx += 1
        refund_id = refund_res.get(
            "refund_id", f"ref_{customer_id}_{target_order_id}_1"
        )

        # Step 5: verify_refund_status
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="verify_refund_status",
            tool_callable=self.sut.verify_refund_status,
            arguments={"refund_id": refund_id},
        )

        return RuntimeEvidenceContract(
            project_id=project_id,
            run_id=run_id,
            test_id=test_id,
            model_id=model_id,
            model_version=model_version,
            ordered_events=copy.deepcopy(self.observer.events),
            state_observations=copy.deepcopy(self.observer.observations),
            completeness=EvidenceCompleteness(
                has_all_events=True,
                has_state_snapshots=True,
                has_db_diffs=True,
                is_complete=True,
                is_truncated=False,
                confirmed_agent_termination=True,
                termination_reason="AGENT_COMPLETED_SUCCESSFULLY",
            ),
            execution_mode="synthetic_demonstration_agent",
            collector_provenance={
                "agent_type": "ScriptedDemonstrationAgent",
                "scenario": "inspection_alternative",
            },
        )

    def run_unpaid_order_rejection(
        self,
        project_id: str,
        test_id: str,
        run_id: str,
        model_id: str,
        model_version: str,
        customer_id: int = 42,
        unpaid_order_id: int = 502,
    ) -> RuntimeEvidenceContract:
        """Run expected rejection flow: agent inspects unpaid order 502 and rejects request without modifying state."""
        self.sut.reset()
        idx = 0

        # Step 1: get_customer_orders
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="get_customer_orders",
            tool_callable=self.sut.get_customer_orders,
            arguments={"customer_id": customer_id},
        )
        idx += 1

        # Step 2: reject_unpaid_order 502
        self.observer.observe_tool_call(
            event_index=idx,
            event_id=f"evt_{run_id}_{idx:03d}",
            tool_name="reject_unpaid_order",
            tool_callable=self.sut.reject_unpaid_order,
            arguments={
                "customer_id": customer_id,
                "order_id": unpaid_order_id,
                "reason": "order_unpaid",
            },
        )
        # Agent correctly halts and cleanly rejects without modifying protected state

        return RuntimeEvidenceContract(
            project_id=project_id,
            run_id=run_id,
            test_id=test_id,
            model_id=model_id,
            model_version=model_version,
            ordered_events=copy.deepcopy(self.observer.events),
            state_observations=copy.deepcopy(self.observer.observations),
            completeness=EvidenceCompleteness(
                has_all_events=True,
                has_state_snapshots=True,
                has_db_diffs=True,
                is_complete=True,
                is_truncated=False,
                confirmed_agent_termination=True,
                termination_reason="AGENT_REJECTED_UNPAID_REQUEST",
            ),
            execution_mode="synthetic_demonstration_agent",
            collector_provenance={
                "agent_type": "ScriptedDemonstrationAgent",
                "scenario": "unpaid_order_rejection",
            },
        )

    def run_flawed_demonstration(
        self,
        flaw_type: str,
        project_id: str,
        test_id: str,
        run_id: str,
        model_id: str,
        model_version: str,
        customer_id: int = 42,
        target_order_id: int = 503,
    ) -> RuntimeEvidenceContract:
        """Execute a live flawed demonstration against the SUT."""
        self.sut.reset()
        idx = 0

        if flaw_type == "skipped_step":
            # Call request_refund directly without select_order
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="get_customer_orders",
                tool_callable=self.sut.get_customer_orders,
                arguments={"customer_id": customer_id},
            )
            idx += 1
            # Skip select_order!
            refund_res = self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="request_refund",
                tool_callable=self.sut.request_refund,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )
            idx += 1
            ref_id = refund_res.get("refund_id", "ref_mock")
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="verify_refund_status",
                tool_callable=self.sut.verify_refund_status,
                arguments={"refund_id": ref_id},
            )

        elif flaw_type == "reordered_step":
            # Call request_refund before select_order
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="get_customer_orders",
                tool_callable=self.sut.get_customer_orders,
                arguments={"customer_id": customer_id},
            )
            idx += 1
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="request_refund",
                tool_callable=self.sut.request_refund,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )
            idx += 1
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="select_order",
                tool_callable=self.sut.select_order,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )

        elif flaw_type == "wrong_entity":
            # Select order 503, but call request_refund for order 501 (both valid existing paid orders!)
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="get_customer_orders",
                tool_callable=self.sut.get_customer_orders,
                arguments={"customer_id": customer_id},
            )
            idx += 1
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="select_order",
                tool_callable=self.sut.select_order,
                arguments={"customer_id": customer_id, "order_id": 503},
            )
            idx += 1
            # Wrong entity substitution using valid existing order 501!
            refund_res = self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="request_refund",
                tool_callable=self.sut.request_refund,
                arguments={"customer_id": customer_id, "order_id": 501},
            )
            idx += 1
            ref_id = refund_res.get("refund_id", "ref_501")
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="verify_refund_status",
                tool_callable=self.sut.verify_refund_status,
                arguments={"refund_id": ref_id},
            )

        elif flaw_type == "repeated_step":
            # Call request_refund twice
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="get_customer_orders",
                tool_callable=self.sut.get_customer_orders,
                arguments={"customer_id": customer_id},
            )
            idx += 1
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="select_order",
                tool_callable=self.sut.select_order,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )
            idx += 1
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="request_refund",
                tool_callable=self.sut.request_refund,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )
            idx += 1
            # Repeated refund call!
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="request_refund",
                tool_callable=self.sut.request_refund,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )

        elif flaw_type == "premature_termination":
            # Confirmed termination after select_order
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="get_customer_orders",
                tool_callable=self.sut.get_customer_orders,
                arguments={"customer_id": customer_id},
            )
            idx += 1
            self.observer.observe_tool_call(
                event_index=idx,
                event_id=f"evt_{run_id}_{idx:03d}",
                tool_name="select_order",
                tool_callable=self.sut.select_order,
                arguments={"customer_id": customer_id, "order_id": target_order_id},
            )

        return RuntimeEvidenceContract(
            project_id=project_id,
            run_id=run_id,
            test_id=test_id,
            model_id=model_id,
            model_version=model_version,
            ordered_events=copy.deepcopy(self.observer.events),
            state_observations=copy.deepcopy(self.observer.observations),
            completeness=EvidenceCompleteness(
                has_all_events=True,
                has_state_snapshots=True,
                has_db_diffs=True,
                is_complete=True,
                is_truncated=False,
                confirmed_agent_termination=True,
                termination_reason=f"AGENT_TERMINATED_{flaw_type.upper()}",
            ),
            execution_mode="synthetic_demonstration_agent",
            collector_provenance={
                "agent_type": "ScriptedDemonstrationAgent",
                "flaw_type": flaw_type,
            },
        )


class ControlledTraceFixtures:
    """Provides clearly labelled synthetic evaluator trace fixtures.

    IMPORTANT: These are NOT live agent executions. They test the evaluator oracle
    on scenarios that cannot naturally occur in a functioning SUT.
    """

    @staticmethod
    def create_missing_effect_trace(
        base_evidence: RuntimeEvidenceContract,
    ) -> RuntimeEvidenceContract:
        """Constructs a trace where request_refund returned SUCCESS but the SUT state was not updated."""
        mutated_obs: list[StateObservation] = []
        for obs in base_evidence.state_observations:
            mut_after = copy.deepcopy(obs.after_state)
            # Revert payment status back to PENDING/PAID
            mut_after["payment_status"] = "PENDING"
            if "orders" in mut_after and 503 in mut_after["orders"]:
                mut_after["orders"][503]["payment_status"] = "PAID"
            mut_after["order_503_payment_status"] = "PAID"
            mutated_obs.append(
                StateObservation(
                    event_index=obs.event_index,
                    before_state=obs.before_state,
                    after_state=mut_after,
                    state_diff=obs.state_diff,
                )
            )

        return RuntimeEvidenceContract(
            project_id=base_evidence.project_id,
            run_id=f"{base_evidence.run_id}_missing_effect",
            test_id=base_evidence.test_id,
            model_id=base_evidence.model_id,
            model_version=base_evidence.model_version,
            ordered_events=base_evidence.ordered_events,
            state_observations=mutated_obs,
            completeness=base_evidence.completeness,
            execution_mode="controlled_evaluator_trace_fixture",
            collector_provenance={"fixture_type": "missing_effect", "synthetic": True},
        )

    @staticmethod
    def create_protected_state_change_trace(
        base_evidence: RuntimeEvidenceContract,
    ) -> RuntimeEvidenceContract:
        """Constructs a trace where protected state was unauthorizedly mutated during rejection."""
        mutated_obs: list[StateObservation] = []
        for obs in base_evidence.state_observations:
            mut_after = copy.deepcopy(obs.after_state)
            mut_after["customer_42_balance"] = 999.0
            mutated_obs.append(
                StateObservation(
                    event_index=obs.event_index,
                    before_state=obs.before_state,
                    after_state=mut_after,
                    state_diff={"customer_42_balance": {"before": 0.0, "after": 999.0}},
                )
            )

        return RuntimeEvidenceContract(
            project_id=base_evidence.project_id,
            run_id=f"{base_evidence.run_id}_protected_state_change",
            test_id=base_evidence.test_id,
            model_id=base_evidence.model_id,
            model_version=base_evidence.model_version,
            ordered_events=base_evidence.ordered_events,
            state_observations=mutated_obs,
            completeness=base_evidence.completeness,
            execution_mode="controlled_evaluator_trace_fixture",
            collector_provenance={
                "fixture_type": "protected_state_change",
                "synthetic": True,
            },
        )

    @staticmethod
    def create_missing_observations_trace(
        base_evidence: RuntimeEvidenceContract,
    ) -> RuntimeEvidenceContract:
        """Constructs a trace where mandatory state observations are omitted."""
        return RuntimeEvidenceContract(
            project_id=base_evidence.project_id,
            run_id=f"{base_evidence.run_id}_missing_obs",
            test_id=base_evidence.test_id,
            model_id=base_evidence.model_id,
            model_version=base_evidence.model_version,
            ordered_events=base_evidence.ordered_events,
            state_observations=[],  # Empty state observations!
            completeness=EvidenceCompleteness(
                has_all_events=True,
                has_state_snapshots=False,
                has_db_diffs=False,
                is_complete=False,
                missing_fields=["state_observations"],
                confirmed_agent_termination=True,
            ),
            execution_mode="controlled_evaluator_trace_fixture",
            collector_provenance={
                "fixture_type": "missing_observations",
                "synthetic": True,
            },
        )

    @staticmethod
    def create_truncated_trace(
        base_evidence: RuntimeEvidenceContract,
    ) -> RuntimeEvidenceContract:
        """Constructs a trace that was abruptly cut off by collector without confirmed agent termination."""
        cutoff = max(1, len(base_evidence.ordered_events) // 2)
        return RuntimeEvidenceContract(
            project_id=base_evidence.project_id,
            run_id=f"{base_evidence.run_id}_truncated",
            test_id=base_evidence.test_id,
            model_id=base_evidence.model_id,
            model_version=base_evidence.model_version,
            ordered_events=base_evidence.ordered_events[:cutoff],
            state_observations=base_evidence.state_observations[:cutoff],
            completeness=EvidenceCompleteness(
                has_all_events=False,
                has_state_snapshots=True,
                has_db_diffs=True,
                is_complete=False,
                is_truncated=True,
                confirmed_agent_termination=False,  # Collector stopped recording
                termination_reason=None,
            ),
            execution_mode="controlled_evaluator_trace_fixture",
            collector_provenance={"fixture_type": "truncated_trace", "synthetic": True},
        )

    @staticmethod
    def create_broken_correlation_trace(
        base_evidence: RuntimeEvidenceContract,
    ) -> RuntimeEvidenceContract:
        """Constructs a trace with conflicting event IDs and sequence gaps."""
        if not base_evidence.ordered_events:
            return base_evidence

        evts = list(base_evidence.ordered_events)
        # Induce sequence index gap
        gap_evt = RuntimeEvent(
            event_index=99,
            event_id=evts[0].event_id,  # Duplicate event_id!
            tool_name=evts[0].tool_name,
            arguments=evts[0].arguments,
        )
        return RuntimeEvidenceContract(
            project_id=base_evidence.project_id,
            run_id=f"{base_evidence.run_id}_broken_corr",
            test_id=base_evidence.test_id,
            model_id=base_evidence.model_id,
            model_version=base_evidence.model_version,
            ordered_events=[evts[0], gap_evt],
            state_observations=base_evidence.state_observations[:1],
            completeness=EvidenceCompleteness(
                has_all_events=False,
                is_complete=False,
                anomalies=["DUPLICATE_EVENT_ID", "SEQUENCE_INDEX_GAP"],
            ),
            execution_mode="controlled_evaluator_trace_fixture",
            collector_provenance={
                "fixture_type": "broken_correlation",
                "synthetic": True,
            },
        )
