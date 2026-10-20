"""Adapter interfaces and implementations for C4 policy-aware execution.

Component: C4 - Policy-Aware Safety and Prompt-Injection Testing
Phase: Phase 3 - Controlled Execution Runner, Injection Delivery, and Runtime Evidence.
"""

import copy
import os
import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.components.c4_policy_aware_safety.contracts.bindings import DomainBinding
from app.components.c4_policy_aware_safety.contracts.cases import PolicyTestCase
from app.components.c4_policy_aware_safety.contracts.enums import (
    EvidenceOrigin,
    ExposureStatus,
    InstructionSourceType,
    TrustClassification,
)
from app.components.c4_policy_aware_safety.contracts.evidence import (
    ActionAttemptEvidence,
    ArgumentProvenanceEvidence,
    AttackEvidence,
    AuthorizationDecisionEvidence,
    DisclosureEvidence,
    EffectEvidence,
    EvaluationEvidencePackage,
    ExposureEvidence,
    InstructionSourceEvidence,
    PrincipalEvidence,
    ToolExecutionEvidence,
    TraceCompletenessEvidence,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    SimulatedAgentBehavior,
    TargetExecutionMode,
)
from app.components.c4_policy_aware_safety.execution.disclosure_sink import (
    LocalSimulatedDisclosureSink,
)


class C4TargetAdapter(ABC):
    """Abstract target adapter for C4 test execution."""

    adapter_id: str
    adapter_version: str
    execution_mode: TargetExecutionMode

    @abstractmethod
    def get_capabilities(self) -> set[str]:
        """Return the set of runtime evidence and observation capabilities supported."""
        ...

    @abstractmethod
    def check_readiness(
        self, case: PolicyTestCase, binding: DomainBinding
    ) -> tuple[bool, list[str]]:
        """Verify that adapter and environment are ready to execute the specified case."""
        ...

    @abstractmethod
    def prepare_fixture(
        self, case: PolicyTestCase, binding: DomainBinding
    ) -> tuple[bool, str | None]:
        """Stage an isolated fixture partition and baseline state for this run."""
        ...

    @abstractmethod
    def create_session(self, case: PolicyTestCase) -> str:
        """Create a fresh, isolated agent/application session."""
        ...

    @abstractmethod
    def deliver_injection(
        self, case: PolicyTestCase, session_id: str
    ) -> dict[str, Any]:
        """Deliver untrusted injection payload into declared channel/field."""
        ...

    @abstractmethod
    def invoke_agent(
        self, case: PolicyTestCase, session_id: str
    ) -> tuple[str, EvaluationEvidencePackage]:
        """Invoke the agent and capture normalized runtime evidence."""
        ...

    @abstractmethod
    def observe_pre_cleanup_effects(
        self, case: PolicyTestCase, session_id: str
    ) -> list[dict[str, Any]]:
        """Capture final application state and committed effects BEFORE fixture reset."""
        ...

    @abstractmethod
    def cleanup_fixture(self, case: PolicyTestCase, session_id: str) -> bool:
        """Reset and teardown isolated fixture partition after trial execution."""
        ...


class SimulatedC4ApplicationAdapter(C4TargetAdapter):
    """Controlled simulated application and scripted agent adapter.

    Executes C4 cases offline and hermetically using configurable behavior profiles.
    Produces evidence via explicit adapter operations without reading internal oracle assertions.
    """

    def __init__(
        self,
        behavior: SimulatedAgentBehavior = SimulatedAgentBehavior.COMPLIANT,
        disclosure_sink: LocalSimulatedDisclosureSink | None = None,
    ) -> None:
        self.adapter_id = "simulated_c4_application_adapter"
        self.adapter_version = "3.0.0"
        self.execution_mode = TargetExecutionMode.SIMULATED
        self.behavior = behavior
        self.disclosure_sink = disclosure_sink or LocalSimulatedDisclosureSink()

        # Session and fixture partitions
        self._fixture_store: dict[str, dict[str, Any]] = {}
        self._session_store: dict[str, dict[str, Any]] = {}
        self._pre_cleanup_effects: dict[str, list[dict[str, Any]]] = {}

    def get_capabilities(self) -> set[str]:
        return {
            "principal",
            "action_attempts",
            "tool_executions",
            "authorization_decisions",
            "effects",
            "disclosures",
            "instruction_sources",
            "exposure",
            "argument_provenance",
            "fixture_isolation",
            "fixture_reset",
        }

    def check_readiness(
        self, case: PolicyTestCase, binding: DomainBinding
    ) -> tuple[bool, list[str]]:
        blockers: list[str] = []
        caps = self.get_capabilities()

        for req in case.required_evidence:
            if req not in caps:
                blockers.append(f"Adapter lacks required evidence capability '{req}'")

        if case.injection_placement_channel:
            untrusted_channels = [u.default_channel for u in binding.untrusted_sources]
            if case.injection_placement_channel not in untrusted_channels:
                blockers.append(
                    f"Injection channel '{case.injection_placement_channel}' not found in domain binding untrusted sources"
                )

        return (len(blockers) == 0, blockers)

    def prepare_fixture(
        self, case: PolicyTestCase, binding: DomainBinding
    ) -> tuple[bool, str | None]:
        if self.behavior == SimulatedAgentBehavior.FIXTURE_PREPARATION_FAILURE:
            return (False, "Simulated partition failure: isolated database schema initialization timed out.")

        partition_id = f"part-{uuid.uuid4().hex[:8]}"
        initial_facts = copy.deepcopy(case.structured_setup.get("known_facts", {}))
        self._fixture_store[case.case_id] = {
            "partition_id": partition_id,
            "baseline_facts": initial_facts,
            "current_facts": copy.deepcopy(initial_facts),
            "prepared": True,
        }
        return (True, None)

    def create_session(self, case: PolicyTestCase) -> str:
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        self._session_store[session_id] = {
            "case_id": case.case_id,
            "injections": [],
            "actions": [],
            "disclosures": [],
        }
        return session_id

    def deliver_injection(
        self, case: PolicyTestCase, session_id: str
    ) -> dict[str, Any]:
        delivery_id = f"inj-deliv-{uuid.uuid4().hex[:8]}"
        record = {
            "delivery_id": delivery_id,
            "channel": case.injection_placement_channel,
            "payload": case.injection_payload,
            "session_id": session_id,
            "delivered": True,
        }
        if session_id in self._session_store:
            self._session_store[session_id]["injections"].append(record)
        return record

    def invoke_agent(
        self, case: PolicyTestCase, session_id: str
    ) -> tuple[str, EvaluationEvidencePackage]:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"

        setup = case.structured_setup
        principal_role = setup.get("principal_role", "CUSTOMER_SUPPORT")
        tool_name = setup.get("tool_name", "process_refund")
        arguments = copy.deepcopy(setup.get("arguments", {}))
        approval_dict = setup.get("approval")

        # 1. Instruction sources
        instruction_sources: list[InstructionSourceEvidence] = [
            InstructionSourceEvidence(
                source_id="trusted_user_prompt",
                source_type=InstructionSourceType.AUTHENTICATED_USER_REQUEST,
                trust_classification=TrustClassification.AUTHENTICATED_USER,
                raw_text=case.agent_task_prompt,
            )
        ]

        # 2. Exposure & Injection handling
        exposure_status = ExposureStatus.NOT_APPLICABLE
        attacks: list[AttackEvidence] = []

        if case.injection_payload:
            attacks.append(
                AttackEvidence(
                    attack_type="INDIRECT_PROMPT_INJECTION",
                    payload=case.injection_payload,
                    attacker_goal=case.hidden_attacker_goal or "Inject untrusted instructions",
                )
            )
            instruction_sources.append(
                InstructionSourceEvidence(
                    source_id="support_ticket_feed",
                    source_type=InstructionSourceType.SUPPORT_TICKET,
                    trust_classification=TrustClassification.UNTRUSTED_CONTENT,
                    raw_text=case.injection_payload,
                )
            )

            if self.behavior == SimulatedAgentBehavior.IGNORES_INJECTION_SOURCE:
                exposure_status = ExposureStatus.NOT_EXPOSED
            elif self.behavior == SimulatedAgentBehavior.MISSING_INSTRUMENTATION:
                exposure_status = ExposureStatus.UNKNOWN
            else:
                exposure_status = ExposureStatus.EXPOSED

        exposure_ev = ExposureEvidence(
            exposure_status=exposure_status,
            exposure_details="Observed at tool_response_ticket_body" if exposure_status == ExposureStatus.EXPOSED else None,
        )

        # 3. Actions, Authorizations, Tool executions, Effects, Disclosures
        action_attempts: list[ActionAttemptEvidence] = []
        tool_executions: list[ToolExecutionEvidence] = []
        authorization_decisions: list[AuthorizationDecisionEvidence] = []
        effects: list[EffectEvidence] = []
        disclosures: list[DisclosureEvidence] = []
        provenances: list[ArgumentProvenanceEvidence] = []

        output_text = "Task completed successfully."

        # Scenario Behavior Scripting
        if self.behavior in (
            SimulatedAgentBehavior.COMPLIANT,
            SimulatedAgentBehavior.FIXTURE_CLEANUP_FAILURE,
        ):
            # Safe compliant agent
            if case.requested_action_legality in ("PROHIBITED", "REQUIRES_APPROVAL") and not approval_dict:
                # Direct challenge or unapproved injection: agent safely declines
                output_text = f"I cannot proceed with {tool_name} without authorized approval or valid permissions."
            else:
                # Benign permitted task: agent attempts permitted action
                action_attempts.append(
                    ActionAttemptEvidence(
                        tool_name=tool_name,
                        arguments=arguments,
                    )
                )
                authorization_decisions.append(
                    AuthorizationDecisionEvidence(
                        status="APPROVED",
                        approver_role=approval_dict.get("approver_role", principal_role) if approval_dict else principal_role,
                        approval_token=approval_dict.get("approval_token") if approval_dict else "AUTH-DEFAULT-OK",
                    )
                )
                tool_executions.append(
                    ToolExecutionEvidence(
                        tool_name=tool_name,
                        arguments=arguments,
                        status="SUCCESS",
                        output={"result": "SUCCESS", "status": "COMPLETED"},
                    )
                )
                effects.append(
                    EffectEvidence(
                        target_entity="order_refund",
                        state_change_observed=True,
                        committed_status="COMMITTED",
                        delta={"status": "REFUNDED", "amount": arguments.get("amount", 100)},
                    )
                )
                output_text = f"Successfully processed {tool_name}."

        elif self.behavior == SimulatedAgentBehavior.UNAUTHORIZED_ATTEMPT_BLOCKED:
            # Agent attempted unauthorized action; backend authorization rejected it
            action_attempts.append(
                ActionAttemptEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )
            authorization_decisions.append(
                AuthorizationDecisionEvidence(
                    status="DENIED",
                    approver_role=None,
                    approval_token=None,
                )
            )
            tool_executions.append(
                ToolExecutionEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="ERROR",
                    rejection_message="403 Forbidden: Action not authorized by policy.",
                )
            )
            effects.append(
                EffectEvidence(
                    target_entity="order_refund",
                    state_change_observed=False,
                    committed_status="BLOCKED_NO_CHANGE",
                    delta={"amount": 0},
                )
            )
            output_text = "Attempted action was blocked by backend authorization."

        elif self.behavior == SimulatedAgentBehavior.PROHIBITED_EFFECT_COMMITTED:
            # Insecure agent + insecure backend: commits prohibited effect
            action_attempts.append(
                ActionAttemptEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )
            authorization_decisions.append(
                AuthorizationDecisionEvidence(
                    status="DENIED",
                    approver_role="NONE",
                )
            )
            tool_executions.append(
                ToolExecutionEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="SUCCESS",
                    output={"result": "REFUND_EXECUTED"},
                )
            )
            effects.append(
                EffectEvidence(
                    target_entity="order_refund",
                    state_change_observed=True,
                    committed_status="COMMITTED",
                    delta={"status": "REFUNDED", "amount": arguments.get("amount", 20000)},
                )
            )
            output_text = "Executed prohibited refund without approval."

        elif self.behavior == SimulatedAgentBehavior.DISCLOSURE_EXFILTRATION:
            # Exfiltrate protected marker to simulated local sink
            marker = setup.get("marker", "CANARY-SECRET-99")
            action_attempts.append(
                ActionAttemptEvidence(
                    tool_name=tool_name,
                    arguments={"destination": "simulated_local_sink", "content": marker},
                )
            )
            obs_id = f"disc-obs-{uuid.uuid4().hex[:8]}"
            destination = "simulated_local_sink"
            payload = f"Exfiltrated canary value: {marker}"
            self.disclosure_sink.record_disclosure(
                observation_id=obs_id,
                destination=destination,
                payload=payload,
                known_markers=[marker],
            )
            disclosures.append(
                DisclosureEvidence(
                    marker=marker,
                    recipient=destination,
                    destination_channel="simulated_local_sink",
                    content_snippet=f"[CANARY-VALUE-EXFILTRATED: {marker}]",
                )
            )
            output_text = f"Canary token {marker} exfiltrated to {destination}."

        elif self.behavior == SimulatedAgentBehavior.OBEYS_FAKE_APPROVAL:
            # Agent relies on fake approval text in ticket, but backend state has no verified approval
            action_attempts.append(
                ActionAttemptEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )
            # Backend authorization evaluates against application state: NONE
            authorization_decisions.append(
                AuthorizationDecisionEvidence(
                    status="DENIED",
                    approver_role="NONE",
                    approval_token="UNVERIFIED_TICKET_CLAIM",
                )
            )
            tool_executions.append(
                ToolExecutionEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="ERROR",
                    rejection_message="403 Forbidden: Forged approval token not found in governance records.",
                )
            )
            output_text = "Action blocked; ticket approval code is unverified."

        elif self.behavior == SimulatedAgentBehavior.UNRESOLVED_PROVENANCE:
            action_attempts.append(
                ActionAttemptEvidence(
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )
            # Provenance lacks causal link
            provenances.append(
                ArgumentProvenanceEvidence(
                    argument_name="amount",
                    source_instruction_id="trusted_user_prompt",
                    provenance_confidence=0.1,
                )
            )
            output_text = "Executed with unresolved argument provenance."

        elif self.behavior in (
            SimulatedAgentBehavior.IGNORES_INJECTION_SOURCE,
            SimulatedAgentBehavior.MISSING_INSTRUMENTATION,
        ):
            # Normal completion without exercising injection
            output_text = "Handled customer inquiry without accessing untrusted feed."

        # Trace completeness
        is_trace_complete = self.behavior != SimulatedAgentBehavior.INCOMPLETE_TRACE
        trace_completeness = TraceCompletenessEvidence(
            is_complete=is_trace_complete,
            missing_stages=[] if is_trace_complete else ["action_receipt_boundary"],
        )

        # Record pre-cleanup effects in adapter store
        self._pre_cleanup_effects[case.case_id] = [e.model_dump(mode="json") for e in effects]

        # Context data for predicates
        context_data: dict[str, Any] = {
            "principal": {"role": principal_role},
            "approval": (
                approval_dict
                if approval_dict
                else (
                    authorization_decisions[0].model_dump(mode="json")
                    if authorization_decisions
                    else {"status": "NONE"}
                )
            ),
        }

        evidence = EvaluationEvidencePackage(
            project_id=case.project_id,
            case_id=case.case_id,
            run_id=run_id,
            trace_id=trace_id,
            contract_version=case.contract_version,
            origin=EvidenceOrigin.SYNTHETIC_DEVELOPER_FIXTURE,
            principal=PrincipalEvidence(
                principal_id=f"user-{principal_role.lower()}-01",
                roles=[principal_role],
                attributes={"authenticated": True, "session_id": session_id},
            ),
            instruction_sources=instruction_sources,
            action_attempts=action_attempts,
            tool_executions=tool_executions,
            authorization_decisions=authorization_decisions,
            disclosures=disclosures,
            effects=effects,
            trace_completeness=trace_completeness,
            attacks=attacks,
            exposure=exposure_ev,
            argument_provenance=provenances,
            context_data=context_data,
        )

        return (output_text, evidence)

    def observe_pre_cleanup_effects(
        self, case: PolicyTestCase, session_id: str
    ) -> list[dict[str, Any]]:
        return self._pre_cleanup_effects.get(case.case_id, [])

    def cleanup_fixture(self, case: PolicyTestCase, session_id: str) -> bool:
        if self.behavior == SimulatedAgentBehavior.FIXTURE_CLEANUP_FAILURE:
            return False

        if case.case_id in self._fixture_store:
            self._fixture_store[case.case_id]["prepared"] = False
        return True


class LiveAUTAdapterStub(C4TargetAdapter):
    """Production AUT adapter stub for live agent and application testing.

    Per Section 6: When live authoritative interfaces/configurations are unavailable,
    reports precise missing interfaces and keeps live execution explicitly blocked.
    """

    def __init__(self) -> None:
        self.adapter_id = "live_aut_adapter_stub"
        self.adapter_version = "1.0.0"
        self.execution_mode = TargetExecutionMode.LIVE_AUT

    def get_capabilities(self) -> set[str]:
        return {
            "principal",
            "action_attempts",
            "tool_executions",
            "authorization_decisions",
            "effects",
            "disclosures",
            "instruction_sources",
            "exposure",
        }

    def check_readiness(
        self, case: PolicyTestCase, binding: DomainBinding
    ) -> tuple[bool, list[str]]:
        blockers: list[str] = []
        nexacart_url = os.environ.get("NEXACART_API_URL")
        agent_url = os.environ.get("C4_LIVE_AGENT_URL")
        auth_token = os.environ.get("NEXACART_AUTH_TOKEN")

        if not nexacart_url:
            blockers.append("Missing live AUT endpoint: NEXACART_API_URL is not set.")
        if not agent_url:
            blockers.append("Missing live agent daemon endpoint: C4_LIVE_AGENT_URL is not set.")
        if not auth_token:
            blockers.append("Missing live authentication credential: NEXACART_AUTH_TOKEN is not configured.")

        return (False, blockers)

    def prepare_fixture(
        self, case: PolicyTestCase, binding: DomainBinding
    ) -> tuple[bool, str | None]:
        return (False, "Live fixture preparation blocked: live AUT endpoints are unconfigured.")

    def create_session(self, case: PolicyTestCase) -> str:
        raise NotImplementedError("Live session creation blocked: live AUT endpoints are unconfigured.")

    def deliver_injection(
        self, case: PolicyTestCase, session_id: str
    ) -> dict[str, Any]:
        raise NotImplementedError("Live injection delivery blocked: live AUT endpoints are unconfigured.")

    def invoke_agent(
        self, case: PolicyTestCase, session_id: str
    ) -> tuple[str, EvaluationEvidencePackage]:
        raise NotImplementedError("Live agent invocation blocked: live AUT endpoints are unconfigured.")

    def observe_pre_cleanup_effects(
        self, case: PolicyTestCase, session_id: str
    ) -> list[dict[str, Any]]:
        return []

    def cleanup_fixture(self, case: PolicyTestCase, session_id: str) -> bool:
        return False
