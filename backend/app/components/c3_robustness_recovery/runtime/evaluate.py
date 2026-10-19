"""Offline evaluation CLI for Component 3 Phase 4 recovery verdicts.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Recovery evaluation using evidence and C2 facts.

Loads local evidence artifacts, validates integrity and linkage, evaluates
recovery rules deterministically, and exports a standalone sanitized evaluation result.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
)
from app.components.c3_robustness_recovery.runtime.evidence import MatchedPairEvidence
from app.components.c3_robustness_recovery.runtime.runner import (
    make_demonstration_candidate_case,
    make_demonstration_recovery_contract,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)


def run_evaluation_cli(args: list[str] | None = None) -> int:
    """Run offline recovery evaluation CLI."""
    parser = argparse.ArgumentParser(
        description="Component 3 Phase 4 Offline Recovery Evaluator",
    )
    parser.add_argument(
        "--evidence-file",
        required=True,
        help="Path to matched pair evidence JSON artifact.",
    )
    parser.add_argument(
        "--c2-facts-file",
        default=None,
        help="Optional path to C2 assertion facts JSON file.",
    )
    parser.add_argument(
        "--export-dir",
        default="evidence_output",
        help="Directory to export evaluation result artifact (default: evidence_output).",
    )
    parser.add_argument(
        "--synthetic-facts",
        action="store_true",
        help="Inject default demonstration fixture C2 facts for testing.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist evaluation result into QA database.",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Override project scope identifier when running in persisted mode.",
    )

    parsed = parser.parse_args(args)
    evidence_path = Path(parsed.evidence_file)

    if not evidence_path.exists():
        print(
            f"Error: Evidence file '{parsed.evidence_file}' not found.", file=sys.stderr
        )
        return 1

    try:
        with open(evidence_path, encoding="utf-8") as f:
            evidence_data = json.load(f)

        evidence = MatchedPairEvidence.model_validate(evidence_data)
    except Exception as exc:  # noqa: BLE001
        print(f"Error loading evidence file: {exc}", file=sys.stderr)
        return 1

    # Load C2 facts
    c2_facts: list[C2AssertionFact] = []
    if parsed.c2_facts_file:
        facts_path = Path(parsed.c2_facts_file)
        if not facts_path.exists():
            print(
                f"Error: C2 facts file '{parsed.c2_facts_file}' not found.",
                file=sys.stderr,
            )
            return 1
        try:
            with open(facts_path, encoding="utf-8") as f:
                facts_data = json.load(f)
            c2_facts = [C2AssertionFact.model_validate(item) for item in facts_data]
        except Exception as exc:  # noqa: BLE001
            print(f"Error loading C2 facts file: {exc}", file=sys.stderr)
            return 1
    elif parsed.synthetic_facts:
        # Provide demonstration facts
        c2_facts = [
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.TRUE,
                provenance="C2_DEMO_FIXTURE",
            )
        ]

    # Reconstruct or resolve case and recovery contracts
    candidate_case = make_demonstration_candidate_case()
    recovery_contract = make_demonstration_recovery_contract()

    eval_request = RecoveryEvaluationRequest(
        project_id=evidence.project_id,
        case_id=evidence.case_id,
        candidate_case=candidate_case,
        recovery_contract=recovery_contract,
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )

    eval_result: RecoveryEvaluationResult = evaluate_recovery(eval_request)

    print("\n================== RECOVERY EVALUATION SUMMARY ==================")
    print(f"Case ID:             {eval_result.case_id}")
    print(f"Pair ID:             {eval_result.pair_id}")
    print(f"Evaluation Status:   {eval_result.evaluation_status.value}")
    verdict_str = (
        eval_result.recovery_verdict.value
        if eval_result.recovery_verdict
        else "None (not evaluated)"
    )
    print(f"Recovery Verdict:    {verdict_str}")
    print(f"Attributed Actor:    {eval_result.actor_attribution}")
    if eval_result.first_violated_rule:
        print(f"First Violated Rule: {eval_result.first_violated_rule}")

    print("\nRule Results:")
    for rule in eval_result.rule_results:
        print(f"  [{rule.status.value}] {rule.rule_id}: {rule.message}")

    if eval_result.non_evaluation_reasons:
        print("\nNon-Evaluation Reasons:")
        for reason in eval_result.non_evaluation_reasons:
            print(f"  - {reason}")

    if eval_result.clean_control_limitations:
        print("\nClean Baseline Limitations:")
        for lim in eval_result.clean_control_limitations:
            print(f"  - {lim}")

    # Export sanitized result artifact
    export_dir = Path(parsed.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_filename = f"eval_{eval_result.pair_id}_{uuid4().hex[:6]}_{ts}.json"
    out_path = export_dir / out_filename

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(eval_result.model_dump(mode="json"), f, indent=2)

    print(f"\nExported evaluation result to: {out_path}")

    if parsed.persist:
        from app.components.c3_robustness_recovery.contracts.persistence import (
            EvaluationComputeRequest,
        )
        from app.components.c3_robustness_recovery.services.storage import (
            compute_and_store_evaluation,
        )
        from app.database import SessionLocal

        if parsed.project_id and parsed.project_id != evidence.project_id:
            print(
                f"Error: Project scope mismatch: Evidence declares project '{evidence.project_id}', "
                f"which does not match specified --project-id '{parsed.project_id}'.",
                file=sys.stderr,
            )
            return 1

        project_id = evidence.project_id
        db = SessionLocal()
        try:
            req = EvaluationComputeRequest(
                project_id=project_id,
                pair_id=evidence.pair_id,
                c2_facts=c2_facts,
            )
            stored_eval = compute_and_store_evaluation(db, req)
            print(
                f"Persisted evaluation to database with ID: {stored_eval.evaluation_id}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Error persisting evaluation to database: {exc}", file=sys.stderr)
            return 1
        finally:
            db.close()

    return 0


if __name__ == "__main__":
    sys.exit(run_evaluation_cli())
