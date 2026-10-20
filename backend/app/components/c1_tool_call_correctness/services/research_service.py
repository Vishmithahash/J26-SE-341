import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.diagnosis import CauseCategory
from app.components.c1_tool_call_correctness.contracts.research import (
    DatasetSplit,
    ReferenceCodeLocation,
    ReferenceLabelImportRequest,
    ReferenceLabelImportResponse,
    ReferenceLabelRecord,
)
from app.components.c1_tool_call_correctness.contracts.results import CorrectnessVerdict
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ReferenceLabelModel,
)


class ResearchService:
    """Manages independent ground truth reference labels and dataset split integrity."""

    def import_reference_labels(
        self,
        db: Session,
        project_id: str,
        request: ReferenceLabelImportRequest,
    ) -> ReferenceLabelImportResponse:
        """Imports independently reviewed reference labels with task_family split isolation."""
        # 1. Check existing task_family splits in DB to prevent split leakage
        existing_family_splits: dict[str, str] = {}
        stmt = select(
            C1ReferenceLabelModel.task_family,
            C1ReferenceLabelModel.dataset_split,
        ).where(C1ReferenceLabelModel.project_id == project_id)
        for fam, split in db.execute(stmt).all():
            existing_family_splits[fam] = split

        # Check internal consistency in incoming batch
        batch_family_splits: dict[str, str] = {}
        for item in request.labels:
            fam = item.task_family
            split = item.dataset_split.value

            # If family already exists in DB, ensure it matches
            if fam in existing_family_splits and existing_family_splits[fam] != split:
                raise ValueError(
                    f"Dataset split leak violation: Task family '{fam}' is already assigned to "
                    f"split '{existing_family_splits[fam]}'. Cannot assign case '{item.case_id}' to split '{split}'."
                )

            # If family has already been seen in this batch, ensure consistency
            if fam in batch_family_splits and batch_family_splits[fam] != split:
                raise ValueError(
                    f"Dataset split leak violation in import batch: Task family '{fam}' has contradictory "
                    f"splits '{batch_family_splits[fam]}' and '{split}'."
                )
            batch_family_splits[fam] = split

        imported_count = 0
        updated_count = 0
        splits_dist: dict[str, int] = {
            DatasetSplit.TRAIN_DEV.value: 0,
            DatasetSplit.VALIDATION.value: 0,
            DatasetSplit.HELD_OUT_TEST.value: 0,
        }
        all_families = set(existing_family_splits.keys())

        # 2. Upsert labels
        for item in request.labels:
            existing = db.scalar(
                select(C1ReferenceLabelModel).where(
                    C1ReferenceLabelModel.project_id == project_id,
                    C1ReferenceLabelModel.case_id == item.case_id,
                    C1ReferenceLabelModel.label_version == item.label_version,
                )
            )

            is_held_out = (
                item.dataset_split == DatasetSplit.HELD_OUT_TEST or item.is_held_out
            )
            locs_json = [
                loc.model_dump(mode="json") for loc in item.ground_truth_code_locations
            ]

            if existing:
                existing.suite_id = item.suite_id
                existing.task_family = item.task_family
                existing.dataset_split = item.dataset_split.value
                existing.ground_truth_verdict = item.ground_truth_verdict.value
                existing.ground_truth_cause = (
                    item.ground_truth_cause.value if item.ground_truth_cause else None
                )
                existing.ground_truth_code_locations = locs_json
                existing.valid_evidence_refs = item.valid_evidence_refs
                existing.reviewer_id = item.reviewer_id
                existing.disagreements = item.disagreements
                existing.adjudication = item.adjudication
                existing.is_held_out = is_held_out
                updated_count += 1
            else:
                new_label = C1ReferenceLabelModel(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    case_id=item.case_id,
                    suite_id=item.suite_id,
                    task_family=item.task_family,
                    dataset_split=item.dataset_split.value,
                    ground_truth_verdict=item.ground_truth_verdict.value,
                    ground_truth_cause=(
                        item.ground_truth_cause.value
                        if item.ground_truth_cause
                        else None
                    ),
                    ground_truth_code_locations=locs_json,
                    valid_evidence_refs=item.valid_evidence_refs,
                    reviewer_id=item.reviewer_id,
                    label_version=item.label_version,
                    disagreements=item.disagreements,
                    adjudication=item.adjudication,
                    is_held_out=is_held_out,
                    created_at=datetime.now(UTC),
                )
                db.add(new_label)
                imported_count += 1

            splits_dist[item.dataset_split.value] = (
                splits_dist.get(item.dataset_split.value, 0) + 1
            )
            all_families.add(item.task_family)

        db.commit()

        return ReferenceLabelImportResponse(
            imported_count=imported_count,
            updated_count=updated_count,
            dataset_splits_distribution=splits_dist,
            task_families_count=len(all_families),
        )

    def list_reference_labels(
        self,
        db: Session,
        project_id: str,
        dataset_split: DatasetSplit | None = None,
        task_family: str | None = None,
        label_version: str | None = None,
    ) -> list[ReferenceLabelRecord]:
        """Queries reference labels matching filters."""
        query = select(C1ReferenceLabelModel).where(
            C1ReferenceLabelModel.project_id == project_id
        )

        if dataset_split:
            query = query.where(
                C1ReferenceLabelModel.dataset_split == dataset_split.value
            )
        if task_family:
            query = query.where(C1ReferenceLabelModel.task_family == task_family)
        if label_version:
            query = query.where(C1ReferenceLabelModel.label_version == label_version)

        records: list[ReferenceLabelRecord] = []
        for row in db.scalars(query).all():
            locs = []
            for l_json in row.ground_truth_code_locations or []:
                try:
                    locs.append(ReferenceCodeLocation.model_validate(l_json))
                except (ValidationError, ValueError, TypeError, KeyError):
                    pass

            cause_enum = None
            if row.ground_truth_cause:
                try:
                    cause_enum = CauseCategory(row.ground_truth_cause)
                except ValueError:
                    cause_enum = None

            records.append(
                ReferenceLabelRecord(
                    id=row.id,
                    project_id=row.project_id,
                    case_id=row.case_id,
                    suite_id=row.suite_id,
                    task_family=row.task_family,
                    dataset_split=DatasetSplit(row.dataset_split),
                    ground_truth_verdict=CorrectnessVerdict(row.ground_truth_verdict),
                    ground_truth_cause=cause_enum,
                    ground_truth_code_locations=locs,
                    valid_evidence_refs=row.valid_evidence_refs or [],
                    reviewer_id=row.reviewer_id,
                    label_version=row.label_version,
                    disagreements=row.disagreements or [],
                    adjudication=row.adjudication or {},
                    is_held_out=row.is_held_out,
                    created_at=row.created_at,
                )
            )
        return records

    def is_case_held_out(self, db: Session, project_id: str, case_id: str) -> bool:
        """Checks if a case belongs to the held-out test split."""
        stmt = select(C1ReferenceLabelModel.is_held_out).where(
            C1ReferenceLabelModel.project_id == project_id,
            C1ReferenceLabelModel.case_id == case_id,
        )
        res = db.scalar(stmt)
        return bool(res)


research_service = ResearchService()
