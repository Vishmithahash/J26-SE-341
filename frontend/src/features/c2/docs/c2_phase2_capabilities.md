# Component 2 Phase 2: Workflow Test Generation, Suite Inspection & Execution Controls

## 1. Executive Summary & Capabilities Classification

Component 2 (C2) provides **State-Aware Multi-Step Workflow Testing** for autonomous agents using Extended Finite State Machine (EFSM) models. Phase 2 delivers automatic coverage-guided workflow test generation, suite and case inspection with 4-category classification, strict private-oracle isolation, and honest execution controls.

### Operations Classification Matrix

| Capability Category | Backend Provider / Implementation | Current Status | Notes & Constraints |
| :--- | :--- | :--- | :--- |
| **Automatic Test Suite Generation** | `TestGenerationService` (`c2_generator_v1`) | **Fully Supported** | Coverage-guided generation from approved EFSM model. Enforces strict schema limits (`extra="forbid"`). |
| **Suite & Case Inspection** | `C2ModelRepository` | **Fully Supported** | Lists suites, cases, pagination, category filtering (`valid`, `alternative`, `negative`, `mutated`), readiness status. |
| **Tester-Private QA Suite Export** | `export_qa_suite` (`/export/qa`) | **Fully Supported** | Contains full reference paths, intermediate guards, expected outcomes, assertions, and mutation provenance for QA testers. |
| **Agent-Safe Payload Export** | `export_agent_task_payloads` (`/export/agent`), `/cases/{id}/agent-payload` | **Fully Supported** | Strictly allowlists only `test_id`, `project_id`, `task`, `fixture_ref`, and `permitted_context`. Redacts all private oracles. |
| **Scripted Synthetic Demonstrations** | `LocalSyntheticRunnerAdapter` (`ScriptedDemonstrationAgent`) | **Fully Supported** | 12 reproducible offline demonstration scenarios with simulated flaw injection and trace recording. |
| **Controlled Evidence Evaluation** | `ConformanceEvaluationEngine` | **Fully Supported** | Evaluates execution trace against EFSM model; detects first divergence, transition violations, and invariant breaches. |
| **Reproducible Re-Evaluation & Replay** | `WorkflowEvaluationService` (`/re-evaluate`, `/verify-reproduction`) | **Fully Supported** | Re-evaluates retained raw evidence digests to confirm deterministic replay reproduction. |
| **Live Agent Execution** | *Requires external LLM runner adapter & live SUT* | **Unavailable** | The backend currently provides `LocalSyntheticRunnerAdapter` (`is_live_execution: false`). No live LLM runner or shared intake service is configured. |

---

## 2. Runner Capabilities & Truthful Execution Disclosure

The frontend explicitly inspects and discloses backend runner capabilities through `LOCAL_RUNNER_CAPABILITIES`:
- **Runner ID**: `local_synthetic_runner_v1`
- **Is Live Execution**: `false`
- **Missing Capabilities**: `live_llm_runner`, `shared_intake_service`, `unified_report_aggregator`
- **Available Observation Capabilities**: `state_snapshots`, `before_after_diffs`, `event_logs`

### Honesty Principles Enforced:
1. **Never Claim Live Agent Execution**: The UI clearly labels all runs as **Synthetic Demonstrations** or **Synthetic Suite Runs**.
2. **No Silent Fallback**: The frontend never pretends a requested live run succeeded by silently substituting a mock demonstration.
3. **No Fabricated Real-Time Telemetry**: Since backend execution endpoints are synchronous, the UI displays an honest waiting spinner (`isExecutingCase`/`isExecutingSuite`) without fabricated progress percentages, fake cancellation buttons, or nonexistent WebSocket subscriptions.
4. **Duplicate Submission Prevention**: Synchronously guarded using `inFlightRef` to prevent double-clicks or repeated network POSTs.

---

## 3. Private Oracle vs Allowlisted Agent Payload

To prevent prompt injection, data leakage, and cheating by autonomous agents, Component 2 enforces a strict boundary between what the QA engineer sees and what the tested agent receives:

```
+---------------------------------------------------------------------------------------+
|                                    C2 TEST DEFINITION                                 |
+---------------------------------------------------------------------------------------+
|  PRIVATE QA ORACLE (Tester Only)             ALLOWLISTED AGENT TASK PAYLOAD           |
|  - Reference Path (Ordered Transitions)      - Test ID                                |
|  - Intermediate Guard Expressions            - Project ID                             |
|  - Expected Outcome (PASS/REJECTION)         - Task Description Prompt                |
|  - Expected Terminal State                   - Fixture Reference                      |
|  - Expected Invariant Assertions             - Permitted Context (e.g. Order ID)      |
|  - Mutation Type & Target Step               -----------------------------------------|
|  - Intended Divergence Location              * STRICTLY REDACTED: All reference       |
|                                                paths, expected states, and assertions |
+---------------------------------------------------------------------------------------+
```

### Mutant Exclusion Rule
Evaluator mutant test cases (`category: "mutated"`, `execution_mode: "synthetic_evaluator_mutant"`) test whether the conformance evaluation engine accurately detects agent flaws. They are **never** exported to tested agents; attempting to export a mutant via `/cases/{test_id}/agent-payload` returns `400 Bad Request`.

---

## 4. API Endpoints & Contract Reference

### Test Generation & Suites
- `POST /api/v1/c2/projects/{project_id}/suites/generate`
  - Body: `GenerateTestSuiteRequest` (`model_id`, `version`, `generator_version`, `seed`, `max_depth`, `max_loop_visits`, `case_budget`, `include_alternatives`, `include_negative_rejections`, `include_mutations`, `mutation_budget`, `enabled_mutation_types`, `fixture_ref`).
  - Gating: Requires the model to have `lifecycle_status === 'APPROVED'` and a valid validation report. Unapproved models return `422 Unprocessable Entity` (`MODEL NOT READY`).
- `GET /api/v1/c2/projects/{project_id}/suites`
  - Returns array of `C2TestSuiteSummaryResponse`.
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}`
  - Returns complete `C2TestSuiteResponse` with planned diagnostics.
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/readiness`
  - Returns `SuiteReadinessResponse` with case readiness breakdown.

### Case Inspection & Exports
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases`
  - Query params: `category` (`valid`, `alternative`, `negative`, `mutated`), `readiness` (`TEST_READY`, `TEST_NOT_READY`).
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}`
  - Returns complete case definition, reference path, assertions, and mutation provenance.
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/export/qa`
  - Returns complete `QASuiteExport` for authorized testers.
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/export/agent`
  - Returns array of allowlisted `AgentTaskPayload` items for live agent tasks.
- `GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/agent-payload`
  - Returns single allowlisted `AgentTaskPayload`. Mutants return HTTP 400.

### Execution & Conformance Evaluation
- `POST /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/run`
  - Executes single test case through backend integration pipeline.
- `POST /api/v1/c2/projects/{project_id}/suites/{suite_id}/run`
  - Bounded suite execution with `max_cases` body parameter.
- `POST /api/v1/c2/projects/{project_id}/demonstrations/run`
  - Executes offline synthetic demonstration with chosen flaw scenario.
- `GET /api/v1/c2/projects/{project_id}/evaluations`
  - Lists evaluation history for active project.
- `GET /api/v1/c2/projects/{project_id}/evidence/{run_id}`
  - Returns retained raw evidence, SHA-256 digest, and execution provenance.
- `POST /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/re-evaluate`
  - Re-evaluates retained raw evidence with optional configuration overrides.
- `POST /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/verify-reproduction`
  - Verifies independent deterministic replay reproduction.

---

## 5. Distinct Execution Verdicts

| Verdict | Meaning | Semantic Category |
| :--- | :--- | :--- |
| **PASS** | Agent trace conformed to all model states, transition guards, and assertions. | Successful compliant run |
| **EXPECTED REJECTION PASS** | Negative test case: SUT correctly rejected an illegal request (e.g. refunding an unpaid order). | Successful negative test |
| **FAIL** | Conformance violation detected: skipped step, swapped order, illegal transition, wrong entity, or missing side-effect. | Conformance failure |
| **INCONCLUSIVE** | Evidence was incomplete, state snapshots were missing, or execution was truncated. | Observability / setup failure |
| **MODEL NOT READY** | Model version was not approved or validation was stale. | Gating rejection (not agent fault) |
| **TEST NOT READY** | Test prerequisites or fixture bindings could not be resolved. | Gating rejection (not agent fault) |
