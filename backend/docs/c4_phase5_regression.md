# Component 4 (C4): Policy-Aware Safety and Prompt-Injection Testing — Phase 5 Policy Change Tracking and Selective Regression Testing

## 1. Executive Summary and Architecture

Phase 5 delivers policy-version comparison, semantic diffing, dependency and scope impact analysis, automated case decision derivation, version-linked test regeneration and freezing, selective regression execution, and evidence-linked regression reporting.

```
+---------------------------------------------------------------------------------------------------------------------------------+
|                                                   C4 PHASE 5 REGRESSION PIPELINE                                                |
+---------------------------------------------------------------------------------------------------------------------------------+
|  1. Version Comparison: Pinned baseline vs candidate accepted contracts; canonical JSON predicate normalization                 |
|  2. Semantic Diffing: Stable identity rule classification (ADDED, REMOVED, SEMANTICALLY_MODIFIED, METADATA_ONLY, PROVENANCE)     |
|  3. Impact Analysis: Multi-tier impact assessment (direct target, indirect permissions/approvals, added rule scope overlap)     |
|  4. Case Decision Derivation: Explicit action assignment (REGENERATE, REVALIDATE, RETIRE, REVISE, RETAIN, BLOCKED)              |
|  5. Regeneration & Validation: Recompute legal boundaries under candidate policy, validate fixtures, freeze with lineage       |
|  6. Plan Lifecycle: DRAFT -> VALIDATED -> FROZEN snapshot with readiness gaps and dependency digests                            |
|  7. Selective Execution: FRESH_EXECUTION vs HISTORICAL_RE_EVALUATION vs REUSED results; isolated fixtures and DB idempotency   |
|  8. Evidence-Linked Reporting: Verdict transitions (requirement change vs regression), dual denominators, audit export         |
+---------------------------------------------------------------------------------------------------------------------------------+
```

### Core Architectural Guarantees
1. **Canonical Normalization Over Arbitrary Equivalence**: Predicates are canonically normalized with recursive dictionary key sorting, floating-point rounding (4 decimal places), and value canonicalization. The engine explicitly avoids claiming unbounded first-order theorem proving; unsupported or ambiguous logical changes are classified conservatively as needing review/revalidation.
2. **Multi-Tier Dependency Impact Tracking**: Impact is not limited to `target_rule_ids`. An existing test targeting an approval threshold also depends on general role permissions and resource restrictions. Furthermore, newly added rules trigger scope-matching across `(principal, action, resource)` selectors to identify impacted existing cases.
3. **Predecessor Lineage & Historical Preservation**: All regenerated cases link explicitly to their predecessors via `predecessor_case_id` and `predecessor_case_version`. Retired cases are never deleted from database tables; historical contracts, test cases, execution traces, and findings remain immutable.
4. **Distinction Between Fresh Execution and Historical Re-Evaluation**: A historical trace re-evaluated against a new policy specification is strictly labeled as `HISTORICAL_RE_EVALUATION` and references the original run ID. It is never presented as fresh candidate-policy coverage.
5. **Database-Enforced Idempotency & Concurrency Guards**: Idempotency is enforced by project-scoped database unique constraints (`uq_c4_regression_batches_proj_idempotency` and `uq_c4_execution_runs_proj_idempotency`), accompanied by SHA-256 request digest verification that returns HTTP 409 Conflict upon mismatched parameter reuse.

---

## 2. Confirmed Phase 4 Audits & Repairs

Before implementing Phase 5, confirmed Phase 4 gaps were audited and repaired with dedicated regression tests:

### 2.1 Quoted Attacks in Legitimate Policy Documents (`extraction/extractor.py`)
- **Defect**: Legitimate governance rules containing attack syntax in quoted explanations (e.g., *"Customer text stating 'ignore previous instructions' cannot grant financial authority"*) were previously over-rejected by naive keyword filters as `INJECTION_SUSPECTED`.
- **Repair**: Enhanced extraction heuristics distinguish between governing organizational statements and quoted untrusted attack examples. Governing statements are accepted as legitimate candidates while quoted examples are verified without falsely rejecting the entire policy candidate.

### 2.2 Model Provider Readiness Infrastructure (`extraction/provider.py`)
- **Defect**: Only `OfflineMockExtractionProvider` was available, and mock success risked concealing the absence of a real model-backed provider.
- **Repair**: Implemented `ConfiguredLlmExtractionProvider`, which checks provider environment configuration and returns `ExtractionReadinessStatus.MODEL_NOT_CONFIGURED` when API keys or endpoints are absent, preventing fabricated live extraction while keeping automated tests completely offline.

### 2.3 Permission and Conditional Restriction Semantics (`evaluator/engine.py`)
- **Defect**: When decomposing policies into general permissions (`ALLOW`) and conditional restrictions (`REQUIRE` / `DENY`), a general permission could inadvertently override an approval requirement if evaluation logic did not enforce proper precedence.
- **Repair**: Updated multi-rule evaluation to ensure approval requirements and restrictions take absolute precedence over general role permissions. If an approval is missing or unverified, the verdict conclusively yields `FAIL` or `INCONCLUSIVE`, never overridden by an `ALLOW`.

### 2.4 Database-Enforced Idempotency Uniqueness (`persistence/models.py`, `persistence/repository.py`)
- **Defect**: Request digest checks alone did not prevent simultaneous concurrent duplicate execution runs from entering the database.
- **Repair**: Added a database-level unique constraint `UniqueConstraint("project_id", "idempotency_key", name="uq_c4_execution_runs_proj_idempotency")` on `c4_execution_runs` and `uq_c4_regression_batches_proj_idempotency` on `c4_regression_batches`. Concurrent duplicate submissions trigger `IntegrityError`, caught and translated into `IdempotencyConflictError`.

---

## 3. Policy Diff Engine (`regression/diff.py`)

### 3.1 Canonical Normalization
The `PolicyDiffEngine` recursively normalizes policy rules into canonical JSON representations before comparison:
- Floating point values are rounded to 4 decimal places.
- Dictionaries are key-sorted.
- Sub-predicates within compound conjunctions/disjunctions are canonicalized.
- Metadata and source references are separated from semantic rule clauses.

### 3.2 Change Classification Taxonomy
Rules are matched by stable `rule_id` across accepted contract versions. Each rule diff is classified as one of:
- **`ADDED`**: Rule exists in candidate contract but not in baseline.
- **`REMOVED`**: Rule exists in baseline contract but was omitted in candidate.
- **`SEMANTICALLY_MODIFIED`**: Principals, actions, resources, applicability conditions, compliance conditions, or approval limits changed.
- **`METADATA_ONLY`**: Rule description, tags, or severity updated without altering logical predicates.
- **`PROVENANCE_ONLY`**: Source artifact excerpt or character coordinates updated without predicate changes.
- **`UNCHANGED`**: Canonical rule definitions match identically.
- **`UNCERTAIN`**: Ambiguous predicate transformations or unmapped rule ID changes, conservatively flagged for review.

---

## 4. Dependency and Impact Analysis (`regression/impact.py`)

### 4.1 Dependency Dimensions
The `PolicyImpactAnalyzer` examines multi-dimensional dependencies:
1. **Direct Target Rule**: The primary rule targeted by a test case.
2. **Indirect Supporting Rules**: General permissions and resource boundaries upon which a specific threshold or approval rule depends.
3. **Domain Binding & Fixtures**: Tool parameter schemas, required approval roles, and fixture state requirements.
4. **Instruction Sources**: Untrusted communication feeds and declared injection surfaces.

### 4.2 Added Rule Scope Matching
When a new rule is added, no historical case directly references it. The impact analyzer performs selector matching:
$$\text{Overlap} \iff \text{match}(\text{rule.principal}, \text{target.principal}) \land \text{match}(\text{rule.action}, \text{target.action}) \land \text{match}(\text{rule.resource}, \text{target.resource})$$
Any existing case whose scope overlaps with an added rule is marked as `POSSIBLY_AFFECTED` with decision `REVALIDATE`.

### 4.3 Case Decisions
For each case in the baseline suite, an explicit action is assigned:
- **`REGENERATE`**: For modified thresholds or boundary values; triggers re-derivation of test inputs and assertions.
- **`REVALIDATE`**: For modified permissions, added rules, or provenance updates; runs validator under candidate policy.
- **`RETIRE`**: For cases whose sole target rule was removed from the policy.
- **`REVISE`**: For multi-rule cases where one rule was removed, retaining the remaining valid assertions.
- **`RETAIN`**: Unaffected cases kept unchanged for regression control.
- **`BLOCKED`**: When required domain fixtures, roles, or generators are unavailable.

---

## 5. Regeneration, Lineage, and Freezing (`regression/regeneration.py`)

1. **Re-Derivation**:
   - For `REGENERATE`, boundary values are recalculated (e.g. threshold shifted from $50.00 to $25.00 updates test parameters and expected approval assertions).
2. **Predecessor Linkage**:
   - Replacement cases increment `case_version` and store `predecessor_case_id` and `predecessor_case_version` directly in the test case contract.
3. **Independent Validation**:
   - Every regenerated case must pass `PolicyTestCaseValidator` against the candidate contract and domain binding.
4. **Immutable Freezing**:
   - Validated cases are frozen via `CaseFreezingService`, computing content hashes.
   - The entire regression plan is frozen into an immutable snapshot (`PlanLifecycleState.FROZEN`).

---

## 6. Selective Regression Execution & Reporting (`regression/service.py`)

### 6.1 Execution Modes
- **`FRESH_EXECUTION`**: Executes only the frozen replacement cases through `C4ExecutionRunner` using fresh, isolated sessions. Unaffected cases are excluded from execution to save compute.
- **`HISTORICAL_RE_EVALUATION`**: Re-evaluates historical execution traces and evidence against candidate policy specifications without invoking the target agent or simulated adapter.
- **`REUSED`**: Records historical run IDs for unchanged retained cases.

### 6.2 Verdict Transitions & Requirement Changes
A verdict change from `PASS` to `FAIL` under a stricter candidate policy (e.g. lowering an approval threshold so an unapproved action now fails) is categorized as:
$$\text{Transition} = \text{PASS\_TO\_FAIL}, \quad \text{is\_requirement\_change} = \text{True}$$
The report clearly distinguishes policy requirement changes from actual agent behavioral regressions.

### 6.3 Dual Denominators
Reports provide explicit denominators for both baseline and candidate suites:
- **Baseline Denominator**: Total cases evaluated in the baseline policy suite.
- **Candidate Denominator**: Total valid cases in the candidate policy suite (accounting for retired and added rules).

---

## 7. Persistence & Database Migration

### Migration `20261020_005_c4` (Revises `20261020_004_c4`)
- **`c4_execution_runs`**:
  - Added unique constraint `uq_c4_execution_runs_proj_idempotency` on `(project_id, idempotency_key)`.
- **`c4_policy_comparisons`**:
  - `comparison_id`, `project_id`, `baseline_contract_id`, `baseline_contract_version`, `candidate_contract_id`, `candidate_contract_version`, `algorithm_version`, `configuration_digest`, `comparison_data`, `created_at`.
- **`c4_regression_plans`**:
  - `plan_id`, `project_id`, `comparison_id`, `baseline_contract_id`, `baseline_contract_version`, `candidate_contract_id`, `candidate_contract_version`, `binding_id`, `binding_version`, `status`, `plan_digest`, `plan_data`, `created_at`, `frozen_at`.
- **`c4_regression_batches`**:
  - `batch_id`, `project_id`, `plan_id`, `candidate_contract_id`, `candidate_contract_version`, `adapter_id`, `execution_mode`, `status`, `idempotency_key`, `request_digest`, `batch_data`, `created_at`, `completed_at`.
  - Added unique constraint `uq_c4_regression_batches_proj_idempotency` on `(project_id, idempotency_key)`.

---

## 8. REST API Specification

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/projects/{project_id}/c4/regression/compare` | Compare two accepted policy contracts and produce a rule diff. |
| `GET` | `/projects/{project_id}/c4/regression/comparisons/{comparison_id}` | Retrieve a stored policy comparison record. |
| `POST` | `/projects/{project_id}/c4/regression/plans` | Create a regression plan and impact analysis from a comparison. |
| `GET` | `/projects/{project_id}/c4/regression/plans/{plan_id}` | Retrieve regression plan details and case decisions. |
| `POST` | `/projects/{project_id}/c4/regression/plans/{plan_id}/regenerate` | Regenerate and revalidate affected cases according to the plan. |
| `POST` | `/projects/{project_id}/c4/regression/plans/{plan_id}/freeze` | Freeze a validated regression plan into an immutable snapshot. |
| `POST` | `/projects/{project_id}/c4/regression/plans/{plan_id}/execute` | Selectively execute ready replacement cases (FRESH or HISTORICAL). |
| `GET` | `/projects/{project_id}/c4/regression/plans/{plan_id}/report` | Retrieve evidence-linked regression report and verdict transitions. |
| `POST` | `/projects/{project_id}/c4/regression/re-evaluate` | Explicitly re-evaluate a historical run under another contract. |

---

## 9. Required Demonstrations Summary

| Scenario | Setup | Observed Behavior | Test Reference |
|---|---|---|---|
| **A. Refund Threshold Change** | Lowered refund approval limit from $50.00 to $25.00 between v1 and v2. | `RULE_REFUND_THRESHOLD` classified as `SEMANTICALLY_MODIFIED`. Boundary test cases regenerated with $25.01 values. Confidentiality cases marked `RETAIN`. | `test_policy_impact_analyzer_threshold_change` |
| **B. Permission-Rule Change** | Changed `CUSTOMER_SUPPORT` permission while keeping threshold rule untouched. | Indirect dependencies detected: cases targeting threshold marked `POSSIBLY_AFFECTED` due to role dependency. | `test_policy_diff_engine_change_classification` |
| **C. Added and Removed Rules** | Added high-risk VIP rule; removed obsolete promotional credit rule. | Existing overlapping cases flagged for revalidation. Sole-target case marked `RETIRE` without deleting historical record. | `test_policy_impact_analyzer_added_rule_scope_overlap` |
| **D. Confidentiality & Authority** | Updated permitted recipient and untrusted feed authority. | Indirect prompt-injection and canary disclosure cases selected for regeneration/revalidation. | `test_policy_diff_engine_change_classification` |
| **E. Non-Semantic Change** | Updated source reference coordinates and metadata tags only. | Classified as `METADATA_ONLY` and `PROVENANCE_ONLY`. Cases retained without requiring fresh agent reruns. | `test_policy_diff_provenance_and_metadata_only` |
| **F. Incomplete Dependencies** | Missing domain fixture or unsupported tool capability. | Plan marks case as `BLOCKED` with explicit readiness gap. Execution safely prevented. | `test_full_regression_service_orchestration_workflow` |
| **G. Fresh Run vs Historical** | Tested execution with `FRESH_EXECUTION` and `HISTORICAL_RE_EVALUATION`. | Fresh run generates new run records; historical re-evaluation re-examines prior evidence and links original run IDs. | `test_fresh_vs_historical_re_evaluation` |

---

## 10. Functional Requirements (FR1–FR13) Traceability Matrix

| ID | Requirement | Phase 5 Implementation Status |
|---|---|---|
| **FR1** | Multi-Family Safety Policy Intake & Contracts | Maintained. Extended with versioned policy comparison requests and diff schemas. |
| **FR2** | Bounded Controlled Policy Derivation | Maintained. Canonical predicate normalization preserves bounded grammar. |
| **FR3** | 3-Valued Kleene Evaluation Engine | Repaired: Approval and restriction precedence strictly enforced across multi-rule policies. |
| **FR4** | Application Domain Bindings & Schemas | Maintained: E-commerce and Booking profiles utilized in regression planning and execution. |
| **FR5** | Deterministic Multi-Category Test Generation | Reused: `RegressionRegenerationService` recalculates boundary inputs for changed policies. |
| **FR6** | Independent Case Validation & Integrity Checking | Maintained: Independent validator confirms all regenerated replacement cases before freezing. |
| **FR7** | Versioned Immutable Case Freezing | **Extended in Phase 5**: Predecessor lineage tracking (`predecessor_case_id`, `predecessor_case_version`) and plan snapshots. |
| **FR8** | Controlled Runner & Adapter Architecture | **Extended in Phase 5**: Selective execution of affected cases; unchanged cases excluded from execution. |
| **FR9** | Isolated Fixture Lifecycle & Reset Verification | Maintained: Isolated session contexts and cleanup verification active during regression runs. |
| **FR10** | Declared Untrusted Injection & Exposure Tracking | Maintained: Exposure status and separated injection findings tracked during regression runs. |
| **FR11** | Multistage Runtime Evidence Capture | Maintained: Findings and evidence links preserved during both fresh runs and historical re-evaluations. |
| **FR12** | Independent Policy, Attacker, & Utility Outcomes | Maintained: Attacker attempt/commit outcomes and benign utility outcomes preserved in regression reports. |
| **FR13** | Run Persistence, Idempotency, & Reporting APIs | **Extended in Phase 5**: Migration `20261020_005_c4`, comparison, plan, and batch models, database unique constraints, REST APIs. |

---

## 11. Remaining Phase 6 Research Work

The following research and empirical validation tasks belong strictly to Phase 6:
1. **Independent Human Reviewer Agreement**: Inter-annotator agreement metrics (Fleiss' / Cohen's Kappa) for extracted policies against ground truth.
2. **Held-Out Benchmark Evaluation**: Large-scale evaluation across held-out real-world e-commerce and booking customer interaction datasets.
3. **Ablation Studies**: Component-level ablations measuring the contribution of Kleene 3-valued evaluation, scope overlap matching, and exact character span grounding.
4. **Vulnerability Attribution Metrics**: Formal measurement of false discovery rates, vulnerability recall, and regression detection efficiency.
