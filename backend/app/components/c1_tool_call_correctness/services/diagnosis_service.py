import time
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    DiagnosisRequest,
    DiagnosisStatus,
    DiagnosisSummary,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1ExecutionRunModel,
)
from app.components.c1_tool_call_correctness.services.diagnosis_engine import (
    DiagnosisEngine,
)
from app.components.c1_tool_call_correctness.services.diagnosis_provider import (
    DeterministicDiagnosisProvider,
    DiagnosisProvider,
    ModelAssistedDiagnosisProvider,
)
from app.components.c1_tool_call_correctness.services.explanation_engine import (
    ExplanationEngine,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    SourceInspectionError,
    SourceInspector,
)


class DiagnosisService:
    """Orchestrates evidence-linked explanations, root-cause diagnosis, and persistence."""

    def __init__(
        self,
        explanation_engine: ExplanationEngine | None = None,
        diagnosis_engine: DiagnosisEngine | None = None,
        default_provider: DiagnosisProvider | None = None,
    ):
        self.explanation_engine = explanation_engine or ExplanationEngine()
        self.diagnosis_engine = diagnosis_engine or DiagnosisEngine()
        self.default_provider = default_provider or DeterministicDiagnosisProvider()

    def _model_to_record(self, model: C1CaseDiagnosisModel) -> CaseDiagnosisRecord:
        return CaseDiagnosisRecord(
            diagnosis_id=model.id,
            project_id=model.project_id,
            run_id=model.run_id,
            case_execution_id=model.case_execution_id,
            case_id=model.case_id,
            attempt_number=model.attempt_number,
            requirement_version=model.requirement_version,
            evaluator_version=model.evaluator_version,
            explanation_version=model.explanation_version,
            status=DiagnosisStatus(model.status),
            cause_category=model.cause_category,
            explanation_summary=model.explanation_summary,
            check_explanations=model.check_explanations,
            candidate_code_locations=model.candidate_code_locations,
            evidence_refs=model.evidence_refs,
            source_hash=model.source_hash,
            explanation_method=model.explanation_method,
            metrics=model.metrics,
            created_at=model.created_at,
        )

    async def execute_diagnosis(
        self,
        db: Session,
        project_id: str,
        run_id: str,
        request: DiagnosisRequest,
        user_id: int | None = None,
    ) -> list[CaseDiagnosisRecord]:
        """Perform batch failure explanation and diagnosis for an execution run."""
        # 1. Check idempotency: If idempotency_key is provided and existing records match, return immediately
        if request.idempotency_key:
            existing_records = (
                db.execute(
                    select(C1CaseDiagnosisModel).filter(
                        C1CaseDiagnosisModel.project_id == project_id,
                        C1CaseDiagnosisModel.run_id == run_id,
                        C1CaseDiagnosisModel.idempotency_key == request.idempotency_key,
                    )
                )
                .scalars()
                .all()
            )
            if existing_records:
                return [self._model_to_record(m) for m in existing_records]

        # 2. Batch-retrieve execution run, case executions, and config in a single query
        retrieval_start = time.perf_counter()
        stmt = (
            select(C1ExecutionRunModel)
            .options(
                joinedload(C1ExecutionRunModel.case_executions),
                joinedload(C1ExecutionRunModel.config),
            )
            .filter(
                C1ExecutionRunModel.project_id == project_id,
                C1ExecutionRunModel.id == run_id,
            )
        )
        run_model = db.execute(stmt).unique().scalar_one_or_none()
        if not run_model:
            raise ValueError(
                f"Execution run '{run_id}' not found for project '{project_id}'."
            )

        retrieval_duration_ms = (time.perf_counter() - retrieval_start) * 1000.0

        # Build tool definitions map
        tools_list = run_model.config.tools if run_model.config else []
        tool_defs: dict[str, ToolDefinition] = {
            t["name"]: ToolDefinition(**t) for t in tools_list
        }

        # Requirement texts for explanations (FR-07: show the relevant requirement)
        requirement_texts = {
            r["req_id"]: {
                "version": r.get("version"),
                "title": r.get("title"),
                "description": r.get("description"),
            }
            for r in ((run_model.config.requirements or []) if run_model.config else [])
            if isinstance(r, dict) and r.get("req_id")
        }

        # Initialize SourceInspector if source_root_path provided
        source_inspector: SourceInspector | None = None
        source_root = request.source_root_path
        if not source_root and run_model.config is not None:
            from app.components.c1_tool_call_correctness.examples.nexacart_live import (
                is_nexacart_connection,
            )
            # NexaCart runs use the server-side source tree of their configuration (the defect lab
            # copy, else NEXACART_SOURCE_ROOT), never a path sent by the browser.
            if is_nexacart_connection(run_model.config.agent_connection_ref):
                from app.components.c1_tool_call_correctness.services.nexacart_correction_service import (
                    nexacart_source_root,
                )

                lab_or_root = nexacart_source_root(run_model.config)
                source_root = str(lab_or_root) if lab_or_root else None
        if source_root and source_root != request.source_root_path:
            try:
                source_inspector = SourceInspector(source_root)
            except SourceInspectionError:
                source_inspector = None  # configured tree missing: no code-level claims
        elif source_root:
            source_inspector = SourceInspector(source_root)

        # Provider selection
        provider = self.default_provider
        if request.use_model_assisted:
            from app.shared.llm.contracts import LLMGenerationRequest
            from app.shared.llm.router import get_llm_service
            from app.shared.llm.service import apply_generation_limits
            llm_service = get_llm_service()
            user_sel = llm_service.get_user_selection(user_id, db) if user_id else None
            model_tag = f"{user_sel.provider}:{user_sel.model_id}" if user_sel else "selected-model"

            async def _c1_model_callable(
                cause_category: str,
                deterministic_summary: str,
                evidence_refs: list[str],
                candidates: list[dict[str, Any]],
            ) -> dict[str, Any]:
                system_prompt = (
                    "You are an AI diagnostic assistant for an Agentic AI QA Framework. "
                    "Explain the diagnosed tool-call failure findings based strictly on the provided evidence. "
                    "Do NOT fabricate non-existent evidence or candidates. "
                    "Return a JSON object conforming to the schema."
                )
                user_prompt = (
                    f"Diagnosed Cause: {cause_category}\n"
                    f"Deterministic Summary: {deterministic_summary}\n"
                    f"Valid Evidence Refs: {evidence_refs}\n"
                    f"Valid Code Candidates: {candidates}\n\n"
                    "Provide a refined explanation summary citing only from the provided valid references."
                )
                schema = {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "cited_evidence": {"type": "array", "items": {"type": "string"}},
                        "cited_candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "function": {"type": "string"},
                                },
                                "required": ["file", "function"],
                            },
                        },
                    },
                    "required": ["summary"],
                }
                gen_req = LLMGenerationRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    operation_reference="c1_diagnosis",
                    prompt_template_version="c1-diagnosis-prompt-v1.0",
                    response_schema=schema,
                    temperature=0.0,
                    max_tokens=1024,
                    # a short rewording needs no reasoning trace; with it qwen3.5 hit the token limit
                    metadata={"ollama_think": False},
                )
                if user_id:
                    gen_res = await llm_service.invoke_for_user(user_id, gen_req, db)
                else:
                    adapter = llm_service.get_adapter(user_sel.provider if user_sel else "ollama")
                    apply_generation_limits(gen_req, {})
                    gen_res = await adapter.generate(gen_req, model_override=user_sel.model_id if user_sel else None)

                if not gen_res.is_success:
                    raise RuntimeError(gen_res.error_message or "Model diagnosis presentation failed")

                out = gen_res.structured_data if isinstance(gen_res.structured_data, dict) else {}
                out["summary"] = out.get("summary") or gen_res.raw_text or deterministic_summary
                out["prompt_tokens"] = gen_res.usage.prompt_tokens or 0
                out["completion_tokens"] = gen_res.usage.completion_tokens or 0
                return out

            from app.config import get_settings

            # The LLM call itself applies the configured limits; the provider must not cut it
            # short (a fixed 5 s window always fell back for local Ollama models).
            provider = ModelAssistedDiagnosisProvider(
                model_callable=_c1_model_callable,
                model_name=model_tag,
                timeout_seconds=get_settings().llm_default_timeout_seconds + 5.0,
            )

        results: list[CaseDiagnosisRecord] = []

        # Filter case executions
        target_case_models = run_model.case_executions
        if request.case_id:
            target_case_models = [
                cm for cm in target_case_models if cm.case_id == request.case_id
            ]
            if not target_case_models:
                raise ValueError(
                    f"Case '{request.case_id}' not found in run '{run_id}'."
                )

        # Process each case execution
        for case_model in target_case_models:
            case_detail = CaseExecutionDetail(
                execution_id=case_model.id,
                case_id=case_model.case_id,
                attempt_number=case_model.attempt_number,
                session_id=case_model.session_id,
                readiness_status=case_model.readiness_status,
                execution_status=case_model.execution_status,
                verdict=case_model.verdict,
                trace_completeness=case_model.trace_completeness,
                resolved_expectations=case_model.resolved_expectations or [],
                agent_task_sent=case_model.agent_task_sent,
                captured_events=case_model.captured_events or [],
                evidence_records=case_model.evidence_records or [],
                raw_trace=case_model.raw_trace or {},
                check_results=case_model.check_results or [],
                error_message=case_model.error_message,
                created_at=case_model.created_at,
                completed_at=case_model.completed_at,
            )

            # Generate deterministic check explanations
            check_explanations = self.explanation_engine.explain_case_checks(
                check_results=case_detail.check_results,
                captured_events=case_detail.captured_events,
                trace_completeness=case_detail.trace_completeness,
                expectations=case_detail.resolved_expectations,
                requirements=requirement_texts,
                task_prompt=case_detail.agent_task_sent.task_prompt
                if case_detail.agent_task_sent
                else None,
            )

            # Diagnose supported root cause
            diagnosis_record = self.diagnosis_engine.diagnose_case(
                project_id=project_id,
                run_id=run_id,
                case_execution=case_detail,
                check_explanations=check_explanations,
                tool_definitions=tool_defs,
                source_inspector=source_inspector,
                expected_code_version=request.code_version,
                retrieval_duration_ms=retrieval_duration_ms,
            )

            # Present diagnosis summary through provider (deterministic or model-assisted)
            presentation_result = await provider.present_diagnosis(diagnosis_record)
            diagnosis_record.explanation_summary = (
                presentation_result.explanation_summary
            )
            diagnosis_record.explanation_method = presentation_result.explanation_method
            if presentation_result.metrics.model_name != "deterministic-rule-engine":
                diagnosis_record.metrics["model_metrics"] = (
                    presentation_result.metrics.model_dump()
                )

            # Check if an existing diagnosis record already exists for this run/case/attempt
            existing_diag = (
                db.execute(
                    select(C1CaseDiagnosisModel).filter(
                        C1CaseDiagnosisModel.run_id == run_id,
                        C1CaseDiagnosisModel.case_id == case_model.case_id,
                        C1CaseDiagnosisModel.attempt_number
                        == case_model.attempt_number,
                        C1CaseDiagnosisModel.explanation_version
                        == diagnosis_record.explanation_version,
                    )
                )
                .scalars()
                .first()
            )

            if existing_diag:
                # Update existing record
                existing_diag.status = diagnosis_record.status.value
                existing_diag.cause_category = diagnosis_record.cause_category.value
                existing_diag.explanation_summary = diagnosis_record.explanation_summary
                existing_diag.check_explanations = [
                    c.model_dump(mode="json")
                    for c in diagnosis_record.check_explanations
                ]
                existing_diag.candidate_code_locations = [
                    c.model_dump(mode="json")
                    for c in diagnosis_record.candidate_code_locations
                ]
                existing_diag.evidence_refs = diagnosis_record.evidence_refs
                existing_diag.source_hash = diagnosis_record.source_hash
                existing_diag.explanation_method = (
                    diagnosis_record.explanation_method.value
                )
                existing_diag.metrics = diagnosis_record.metrics
                existing_diag.idempotency_key = request.idempotency_key
                db.flush()
                results.append(self._model_to_record(existing_diag))
            else:
                # Insert new diagnosis model
                new_diag = C1CaseDiagnosisModel(
                    id=diagnosis_record.diagnosis_id,
                    project_id=project_id,
                    run_id=run_id,
                    case_execution_id=case_model.id,
                    case_id=case_model.case_id,
                    attempt_number=case_model.attempt_number,
                    requirement_version=diagnosis_record.requirement_version,
                    evaluator_version=diagnosis_record.evaluator_version,
                    explanation_version=diagnosis_record.explanation_version,
                    status=diagnosis_record.status.value,
                    cause_category=diagnosis_record.cause_category.value,
                    explanation_summary=diagnosis_record.explanation_summary,
                    check_explanations=[
                        c.model_dump(mode="json")
                        for c in diagnosis_record.check_explanations
                    ],
                    candidate_code_locations=[
                        c.model_dump(mode="json")
                        for c in diagnosis_record.candidate_code_locations
                    ],
                    evidence_refs=diagnosis_record.evidence_refs,
                    source_hash=diagnosis_record.source_hash,
                    explanation_method=diagnosis_record.explanation_method.value,
                    metrics=diagnosis_record.metrics,
                    idempotency_key=request.idempotency_key,
                )
                db.add(new_diag)
                db.flush()
                results.append(self._model_to_record(new_diag))

        db.commit()
        return results

    def get_diagnosis_by_id(
        self, db: Session, project_id: str, diagnosis_id: str
    ) -> CaseDiagnosisRecord | None:
        """Retrieve a stored diagnosis record by diagnosis ID."""
        model = (
            db.execute(
                select(C1CaseDiagnosisModel).filter(
                    C1CaseDiagnosisModel.project_id == project_id,
                    C1CaseDiagnosisModel.id == diagnosis_id,
                )
            )
            .scalars()
            .first()
        )
        if not model:
            return None
        return self._model_to_record(model)

    def get_case_diagnosis(
        self, db: Session, project_id: str, run_id: str, case_id: str
    ) -> CaseDiagnosisRecord | None:
        """Retrieve latest diagnosis for a specific case execution in a run."""
        model = (
            db.execute(
                select(C1CaseDiagnosisModel)
                .filter(
                    C1CaseDiagnosisModel.project_id == project_id,
                    C1CaseDiagnosisModel.run_id == run_id,
                    C1CaseDiagnosisModel.case_id == case_id,
                )
                .order_by(desc(C1CaseDiagnosisModel.attempt_number))
            )
            .scalars()
            .first()
        )
        if not model:
            return None
        return self._model_to_record(model)

    def get_candidate_code_locations(
        self, db: Session, project_id: str, diagnosis_id: str
    ) -> list[CandidateCodeLocation]:
        """Retrieve evidence-linked candidate code locations for a diagnosis."""
        diag = self.get_diagnosis_by_id(db, project_id, diagnosis_id)
        if not diag:
            raise ValueError(f"Diagnosis '{diagnosis_id}' not found.")
        return diag.candidate_code_locations

    def list_diagnoses(
        self,
        db: Session,
        project_id: str,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[DiagnosisSummary]:
        """Inspect diagnosis history for a project or run."""
        stmt = (
            select(C1CaseDiagnosisModel)
            .filter(C1CaseDiagnosisModel.project_id == project_id)
            .order_by(desc(C1CaseDiagnosisModel.created_at))
            .limit(limit)
        )
        if run_id:
            stmt = stmt.filter(C1CaseDiagnosisModel.run_id == run_id)

        models = db.execute(stmt).scalars().all()
        return [
            DiagnosisSummary(
                diagnosis_id=m.id,
                project_id=m.project_id,
                run_id=m.run_id,
                case_execution_id=m.case_execution_id,
                case_id=m.case_id,
                attempt_number=m.attempt_number,
                cause_category=m.cause_category,
                explanation_summary=m.explanation_summary,
                candidate_count=len(m.candidate_code_locations or []),
                status=DiagnosisStatus(m.status),
                created_at=m.created_at,
            )
            for m in models
        ]
