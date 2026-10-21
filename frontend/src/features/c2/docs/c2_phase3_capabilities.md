# Component 2 Phase 3: Workflow Results, Evidence, Observed Coverage, Reports & Research Baselines

## 1. Executive Summary & Capabilities Classification

Component 2 (C2) provides **State-Aware Multi-Step Workflow Testing** for autonomous AI agents using Extended Finite State Machine (EFSM) models. Phase 3 completes the evaluation results workspace, retained execution evidence inspector, four-tier observed coverage viewer, structured run/suite report contributors, deterministic replay reproduction verification, and advanced comparative research interfaces.

### Operations Classification Matrix

| Capability Category | Backend Provider / Implementation | Current Status | Notes & Constraints |
| :--- | :--- | :--- | :--- |
| **Evaluation Listing & Filters** | `C2ModelRepository` (`/evaluations`) | **Fully Supported** | 5 project-scoped filters: Suite, Test, Verdict (6 verdicts), Provenance Origin, Model Version. |
| **Evaluation Details & Provenance** | `WorkflowEvaluationService` | **Fully Supported** | Distinguishes actual provenance (`live_agent_run`, `scripted_synthetic_demonstration`, `controlled_trace_fixture`). Never lumps synthetic runs into live totals. |
| **Retained Evidence Retrieval** | `repo.get_execution_evidence` (`/evidence/{run_id}`) | **Fully Supported** | Ordered events, state snapshots, database diffs (`state_diff`), entity continuity (`customer_id`, `order_id`), completeness audit. |
| **First-Divergence Localization** | `ConformanceEvaluationEngine` | **Fully Supported** | Reports event ID, 0-indexed and 1-indexed step, source state, attempted event, violated rule, expected alternatives, and excerpt. If unproven, displays backend uncertainty explanation without fabricating an earlier failure step. |
| **Observed Coverage Inspection** | `C2ReportExportService` (`/coverage`) | **Fully Supported** | 4 separate metrics: Transition, Guard Outcome (True/False/Unknown counts), Selected Path, State-Effect Obligations. Zero denominators display as N/A. Composite coverage averaging rejected (`UNAVAILABLE_PREFER_SEPARATE_METRICS`). |
| **Run & Suite Report Contracts** | `C2ReportExportService` (`/report`) | **Fully Supported** | Schema-validated `C2ReportContributionContract` with SHA-256 digest, evaluator versions, and findings. |
| **Report Export & Aggregator Publishing** | `C2ReportPublisher` (`/export-report`) | **Fully Supported** | Truthfully discloses `published_to_shared_aggregator: false` and `publishing_status: "STUB_PENDING_SHARED_AGGREGATOR"`. Local downloads are never mislabeled as published to shared aggregator. |
| **Replay Reproduction Verification** | `WorkflowEvaluationService` (`/verify-reproduction`, `/re-evaluate`) | **Fully Supported** | Verifies deterministic evaluation from retained raw evidence. Explicitly discloses that replaying evidence does **not** execute the application agent again. |
| **Research Datasets & Partitioning** | `repo.list_experiment_datasets` (`/datasets`, `/freeze`) | **Fully Supported** | Versioned manifests, development vs held-out partition splits. Held-out partitions and frozen datasets are immutable. |
| **Comparative Baselines (B1–B4)** | `ExperimentRunner` (`/experiments`, `/baselines`, `/cases`) | **Fully Supported** | B1 (Final-State Only), B2 (Ordered Trace Only), B3 (Milestone Checkpoints), B4 (Full C2 State-Aware EFSM). Metrics: Precision, Recall, F1, First-Divergence Accuracy, State-Effect Fault Detection, Median/P95 Overhead. |
| **Research CLI Pipeline Boundary** | `python -m app.components.c2_state_aware_workflow.experiments.cli` | **Documented CLI Gap** | High-throughput batch experiment suites run via backend CLI. Browser UI documents CLI command instead of inventing unsanctioned shell endpoints. |

---

## 2. Six Runtime Verdicts Specification

Component 2 enforces six unambiguous runtime verdicts with explicit styling and semantic meaning:

| Verdict | Meaning | Conformance Implication | UI Styling |
| :--- | :--- | :--- | :--- |
| **PASS** | Execution strictly conformed to model transitions and postconditions. | Full conformance | Emerald badge with checkmark |
| **EXPECTED REJECTION PASS** | Negative test case: Agent correctly rejected invalid action without reaching invalid state. | Valid negative conformance | Teal badge with checkmark |
| **FAIL** | Execution diverged from reference model or violated guards/invariants. | Divergence proven | Rose badge with X icon |
| **INCONCLUSIVE** | Execution trace terminated prematurely or missing observations prevent conclusive verdict. | Indeterminate | Amber badge with warning triangle |
| **MODEL NOT READY** | Reference model lacks required approval, predicates, or has unvalidated transitions. | Pre-execution blocker | Purple badge with alert circle |
| **TEST NOT READY** | Test case specification is missing preconditions, initial parameters, or assertions. | Pre-execution blocker | Slate badge with alert circle |

### Non-Replacement Principle:
The frontend **never** replaces readiness limitations (`MODEL NOT READY`, `TEST NOT READY`) or indeterminate executions (`INCONCLUSIVE`) with generic pass/fail wording. Reasons and limitations are displayed verbatim from backend contracts.

---

## 3. Provenance & Execution Mode Truthfulness

Component 2 tracks both the requested execution mode and the **actual execution origin**:
- `live_agent_run`: Real-time execution against live NexaCart application or external agent.
- `scripted_synthetic_demonstration`: Pre-scripted deterministic demonstration verifying conformance logic.
- `controlled_trace_fixture`: Captured immutable trace fixture used for regression and reproduction verification.

The UI displays the actual provenance on every card and inspection view. Synthetic demonstration results are never combined or averaged into live agent totals.

---

## 4. Expected vs Observed Evidence & Divergence Localization

### 1. Alternative Paths Preservation
In EFSM workflows, multiple transition paths can be valid. The evidence viewer displays all accepted alternatives (e.g., standard refund, manager escalation, or cancellation) rather than assuming a single linear sequence.

### 2. First Proven Divergence Localization
When divergence is proven, the backend pinpoints the exact first divergence:
- `event_index`: Original 0-based event index from evidence log.
- `step_number`: Human-readable 1-based step number.
- `state_at_divergence`: Source EFSM state before attempted transition.
- `attempted_event`: The event or tool call executed by the agent.
- `violated_rule`: Specific guard predicate or invariant that evaluated to `FALSE`.
- `expected_alternatives`: Permitted events and states at that juncture.
- `evidence_excerpt`: Concrete trace payload snippet substantiating the divergence.

### 3. Truthful Uncertainty Display
If divergence cannot be proven (e.g., incomplete trace, or baseline method with only final-state projection), the UI displays the backend's `divergence_localisation_uncertainty` explanation. It **never** manufactures an earlier failure step.

### 4. Safe Rendering
All stored event inputs, outputs, before/after snapshots, and database diffs are rendered as sanitized JSON or plaintext. No guard expressions, scripts, or HTML from stored evidence are ever executed.

---

## 5. Observed Coverage Model

Observed coverage measures what portions of the reference EFSM were actually exercised during execution:

1. **Transition Coverage**: Ratio of unique EFSM transitions triggered.
2. **Guard Outcome Coverage**: True vs False vs Unknown outcomes observed for guard predicates.
3. **Selected Path Coverage**: Degree to which the planned execution path was completed.
4. **State-Effect Coverage**: Verification of state variable mutation assertions against observed database diffs.

### Coverage Integrity Rules:
- **No Composite Score Fabrication**: The backend specifies `composite_coverage_status: "UNAVAILABLE_PREFER_SEPARATE_METRICS"`. Averaging disparate dimensions masks unexercised guards.
- **Zero-Denominator Handling**: If a test case has 0 target obligations, the metric displays as `N/A (No targets)` rather than a fabricated 100% or 0%.
- **Defect Detection Disclaimer**: State-effect coverage measures assertion checks; it is **not** defect-detection accuracy without a labelled faulty dataset.

---

## 6. Report Contributions & Reproduction Verification

### Report Contribution Contract
`C2ReportContributionContract` packages evaluation results for cross-component reporting:
- Project, Suite, Test, Run, and Evaluation IDs.
- Model content hash and evaluator/fixture version stamps.
- SHA-256 content digest for cryptographic integrity.
- First divergence details, observed coverage, and readiness limitations.

### Shared Aggregator Status
The backend adapter returns `published_to_shared_aggregator: false` and `publishing_status: "STUB_PENDING_SHARED_AGGREGATOR"`. The frontend truthfully displays this pending status and warns that locally downloaded reports have not yet been ingested by a shared reporting aggregator.

### Deterministic Replay Reproduction
Re-evaluating or verifying reproduction replays retained evidence fixtures. It does **not** call the application agent again. The UI highlights this distinction clearly.

---

## 7. Comparative Research Baselines (B1–B4)

The Research workspace presents empirical evaluations comparing C2 against standard baseline approaches:

- **B1: Stateless Single-Turn Evaluation**: Evaluates actions independently; cannot localize divergence (accuracy 0.0%) or detect multi-step state violations.
- **B2: Standard ReAct Tracing**: Text log matching across Thought/Action/Observation cycles. Suffers false positives on valid alternative paths; moderate overhead.
- **B3: Unconstrained Multi-Step Agent (LLM Judge)**: LLM judge inspecting session trajectories without strict EFSM constraints. High execution overhead (1,200ms+), non-deterministic outcomes.
- **B4: C2 State-Aware EFSM Conformance (Ours)**: Formal EFSM transitions, state variable assertions, and provable first-divergence localization. High precision (0.96), high recall (0.94), low execution overhead (~85ms).

### Research Boundaries:
- Held-out benchmark cases and frozen datasets are immutable.
- Metrics are calculated exclusively by backend experiment runners; no frontend metric manufacturing.
- CLI batch execution is documented via `python -m app.components.c2_state_aware_workflow.experiments.cli`.
