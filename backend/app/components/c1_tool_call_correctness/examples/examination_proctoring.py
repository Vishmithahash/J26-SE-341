from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
    ProjectConfigCreate,
    ResetCapability,
    TaskRequirement,
    ToolConstraints,
    ToolDefinition,
    ToolParameterSchema,
    TraceCapability,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
    ExpectationSuite,
    FieldPresence,
    SourceDataRelationship,
    SourceRelationshipType,
    ToolSelectionExpectation,
)

# ==============================================================================
# SYNTHETIC BENCHMARK FIXTURE - NOT EVIDENCE OF REAL-DOMAIN TRANSFERABILITY
# This fixture is a synthetic examination domain specification designed to evaluate
# tool-call correctness testing algorithms under simulated proctoring constraints.
# It should not be treated as empirical evidence of real-world exam security or
# cross-domain transferability without live pilot validation.
# ==============================================================================

EXAM_USER_REQUEST = (
    "Candidate #CAND-5012 has checked in for Exam #EXAM-9901 (Advanced Algorithms). "
    "Verify the candidate's government ID and face biometric match, then dispatch the encrypted question paper. "
    "If an unapproved peripheral or secondary monitor is detected, flag suspicious activity before paper release."
)

EXAM_FIXTURE_DATA: dict[str, Any] = {
    "fixture_candidate_5012": {
        "candidate_id": "CAND-5012",
        "exam_id": "EXAM-9901",
        "id_document_hash": "id_doc_sha256_90214a",
        "biometric_confidence_score": 0.98,
        "environment_checks": {
            "webcam_active": True,
            "microphone_active": True,
            "secondary_monitors": 0,
            "unapproved_processes": [],
        },
        "session_status": "READY_FOR_PAPER",
    }
}


def get_examination_proctoring_example_config() -> ProjectConfigCreate:
    """Returns a synthetic, production-grade example configuration for the examination proctoring domain."""
    tools = [
        ToolDefinition(
            name="verify_candidate_identity",
            description="Verifies candidate credentials, photo ID match, and active biometric baseline.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "candidate_id": {
                        "type": "string",
                        "description": "Unique candidate identifier, e.g. CAND-5012",
                    },
                    "exam_id": {
                        "type": "string",
                        "description": "Target examination identifier, e.g. EXAM-9901",
                    },
                    "min_confidence_threshold": {
                        "type": "number",
                        "description": "Minimum acceptable face-match score [0.0 - 1.0].",
                    },
                },
                required=["candidate_id", "exam_id"],
            ),
        ),
        ToolDefinition(
            name="flag_suspicious_activity",
            description="Logs a proctoring anomaly, attaches evidence frames, and pauses exam progression.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "candidate_id": {"type": "string"},
                    "anomaly_type": {
                        "type": "string",
                        "enum": [
                            "MULTIPLE_FACES",
                            "NO_FACE_DETECTED",
                            "SECONDARY_SCREEN",
                            "AUDIO_SPEECH_DETECTED",
                        ],
                    },
                    "evidence_token": {"type": "string"},
                },
                required=["candidate_id", "anomaly_type"],
            ),
        ),
        ToolDefinition(
            name="dispatch_exam_paper",
            description="Releases the time-locked question paper token once all identity and room checks pass.",
            parameters_schema=ToolParameterSchema(
                type="object",
                properties={
                    "candidate_id": {"type": "string"},
                    "exam_id": {"type": "string"},
                    "paper_token": {"type": "string"},
                    "time_limit_minutes": {"type": "integer"},
                },
                required=["candidate_id", "exam_id", "paper_token"],
            ),
        ),
    ]

    requirements = [
        TaskRequirement(
            req_id="REQ-EXAM-ID-01",
            version="1.0",
            title="Candidate Identity Verification",
            description="Candidate identity must be explicitly validated with confidence >= 0.95 before paper release.",
            category="safety",
        ),
        TaskRequirement(
            req_id="REQ-EXAM-SECURITY-02",
            version="1.0",
            title="Room Security Check",
            description="Paper must never be released if secondary display or unapproved peripherals are detected.",
            category="safety",
        ),
        TaskRequirement(
            req_id="REQ-EXAM-RELEASE-03",
            version="1.0",
            title="Paper Release Binding",
            description="Paper dispatch must match the candidate ID and exam ID exactly as registered.",
            category="business_logic",
        ),
    ]

    tool_constraints = ToolConstraints(
        permitted_tools=[
            "verify_candidate_identity",
            "flag_suspicious_activity",
            "dispatch_exam_paper",
        ],
        required_tools=["verify_candidate_identity", "dispatch_exam_paper"],
        forbidden_tools=["admin_override_exam", "delete_proctoring_logs"],
        max_invocations={"dispatch_exam_paper": 1},
    )

    expectations = ExpectationSuite(
        tool_selections=[
            ToolSelectionExpectation(
                tool_name="verify_candidate_identity",
                is_required=True,
                min_count=1,
                must_precede_tools=["dispatch_exam_paper"],
                requirement_refs=["REQ-EXAM-ID-01"],
            ),
            ToolSelectionExpectation(
                tool_name="dispatch_exam_paper",
                is_required=True,
                min_count=1,
                max_count=1,
                requirement_refs=["REQ-EXAM-RELEASE-03"],
            ),
        ],
        argument_constraints={
            "verify_candidate_identity": [
                ArgumentConstraint(
                    argument_name="candidate_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="CAND-5012",
                    requirement_ref="REQ-EXAM-ID-01",
                ),
                ArgumentConstraint(
                    argument_name="exam_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="EXAM-9901",
                    requirement_ref="REQ-EXAM-ID-01",
                ),
            ],
            "dispatch_exam_paper": [
                ArgumentConstraint(
                    argument_name="candidate_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="CAND-5012",
                    requirement_ref="REQ-EXAM-RELEASE-03",
                ),
                ArgumentConstraint(
                    argument_name="exam_id",
                    presence=FieldPresence.REQUIRED_NON_NULL,
                    expected_type="string",
                    operator=ComparisonOperator.EQUALS,
                    expected_value="EXAM-9901",
                    requirement_ref="REQ-EXAM-RELEASE-03",
                ),
            ],
        },
        source_relationships={
            "verify_candidate_identity": [
                SourceDataRelationship(
                    source_record_id="fixture_candidate_5012",
                    source_path="candidate_id",
                    relationship_type=SourceRelationshipType.EXACT_MATCH,
                )
            ]
        },
    )

    return ProjectConfigCreate(
        agent_connection_ref="simulated://exam-proctor-agent-v1",
        tools=tools,
        requirements=requirements,
        tool_constraints=tool_constraints,
        expectations=expectations.model_dump(),
        synthetic_fixture_refs=["fixture_candidate_5012"],
        reset_capability=ResetCapability(
            capability_ref="exam_reset_hook",
            hook_type="STATE_RESET",
            is_idempotent=True,
            details={"state_keys": ["candidate_session"]},
        ),
        trace_capabilities=[
            TraceCapability(
                channel=EvidenceChannel.TOOL_CALL_LOG,
                description="Recorded tool call logs and arguments",
                enabled=True,
            )
        ],
    )
