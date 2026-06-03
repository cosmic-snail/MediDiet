from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from knowledge.dataset_manifest import sha256_text


class AnnotationSplit(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    HOLDOUT = "holdout"


class AnnotationStatus(str, Enum):
    DRAFT = "draft"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"


ANNOTATION_FILE_NAME = "expert_annotations.jsonl"
EXPERT_GOLD_FILE_NAME = "gold_expert_evaluation_set.jsonl"
EXPERT_GOLD_SPLIT_FILE_NAMES = {
    AnnotationSplit.TRAIN.value: "gold_expert_train.jsonl",
    AnnotationSplit.DEV.value: "gold_expert_dev.jsonl",
    AnnotationSplit.TEST.value: "gold_expert_test.jsonl",
    AnnotationSplit.HOLDOUT.value: "gold_expert_holdout.jsonl",
}
EXPERT_GOLD_SOURCE = "expert_annotation"
EXPERT_OFFLINE_EVALUATION_ONLY = "expert_offline_evaluation_only"


def build_annotation_queue(dataset_dir: Path) -> list[dict[str, Any]]:
    manifest_rows = _load_jsonl(dataset_dir / "manifest.jsonl")
    silver_expected_by_doc_id = {
        str(expected_row.get("doc_id")): expected_row
        for expected_row in _load_jsonl(dataset_dir / "expected_rules.jsonl")
    }
    latest_by_doc_id = latest_annotations_by_doc_id(dataset_dir)

    queue_records: list[dict[str, Any]] = []
    for manifest_row in manifest_rows:
        doc_id = str(manifest_row["doc_id"])
        source_card_path = _resolve_source_card_path(dataset_dir, manifest_row)
        source_text = source_card_path.read_text(encoding="utf-8")
        queue_records.append(
            {
                "doc_id": doc_id,
                "title": manifest_row.get("title", doc_id),
                "language": manifest_row.get("language", ""),
                "source_type": manifest_row.get("source_type", ""),
                "source_url": manifest_row.get("source_url", ""),
                "source_card_path": str(source_card_path),
                "source_card_hash": sha256_text(source_text),
                "source_text": source_text,
                "manifest": manifest_row,
                "silver_expected": silver_expected_by_doc_id.get(doc_id),
                "latest_annotation": latest_by_doc_id.get(doc_id),
            }
        )
    return queue_records


def latest_annotations_by_doc_id(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    latest_by_doc_id: dict[str, dict[str, Any]] = {}
    for annotation_record in load_expert_annotations(dataset_dir):
        doc_id = str(annotation_record.get("doc_id") or "")
        if doc_id:
            latest_by_doc_id[doc_id] = annotation_record
    return latest_by_doc_id


def load_expert_annotations(dataset_dir: Path) -> list[dict[str, Any]]:
    return _load_jsonl(dataset_dir / ANNOTATION_FILE_NAME)


def append_expert_annotation(*, dataset_dir: Path, annotation: dict[str, Any]) -> dict[str, Any]:
    queue_records_by_doc_id = {record["doc_id"]: record for record in build_annotation_queue(dataset_dir)}
    doc_id = str(annotation.get("doc_id") or "")
    if doc_id not in queue_records_by_doc_id:
        raise ValueError(f"unknown doc_id for expert annotation: {doc_id}")
    _validate_annotation_boundaries(annotation)
    _validate_source_hash(annotation, queue_records_by_doc_id[doc_id])
    _validate_evidence_quotes(annotation, queue_records_by_doc_id[doc_id])

    annotation_record = {
        **annotation,
        "annotation_id": annotation.get("annotation_id") or f"expert_annotation_{doc_id}_{uuid.uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "annotation_schema_version": "expert-annotation-v1",
    }
    annotation_path = dataset_dir / ANNOTATION_FILE_NAME
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    with annotation_path.open("a", encoding="utf-8") as annotation_file:
        annotation_file.write(json.dumps(annotation_record, ensure_ascii=False, sort_keys=True) + "\n")
    return annotation_record


def freeze_expert_gold_annotations(
    *,
    dataset_dir: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    queue_records_by_doc_id = {record["doc_id"]: record for record in build_annotation_queue(dataset_dir)}
    approved_latest_records = [
        annotation_record
        for annotation_record in latest_annotations_by_doc_id(dataset_dir).values()
        if annotation_record.get("annotation_status") == AnnotationStatus.APPROVED.value
    ]
    gold_rows: list[dict[str, Any]] = []
    for annotation_record in sorted(approved_latest_records, key=lambda record: str(record.get("doc_id", ""))):
        doc_id = str(annotation_record.get("doc_id"))
        queue_record = queue_records_by_doc_id.get(doc_id)
        if not queue_record:
            raise ValueError(f"unknown doc_id in expert annotation: {doc_id}")
        if annotation_record.get("source_card_hash") != queue_record.get("source_card_hash"):
            raise ValueError(f"stale source hash for {doc_id}; rerun expert review before freezing gold")
        gold_rows.append(_annotation_to_expert_gold_row(annotation_record))

    gold_path = output_path or (dataset_dir / EXPERT_GOLD_FILE_NAME)
    _write_jsonl(gold_path, gold_rows)
    split_gold_paths = _write_split_gold_files(dataset_dir=dataset_dir, gold_rows=gold_rows)
    return {
        "dataset_id": dataset_dir.name,
        "gold_path": str(gold_path),
        "split_gold_paths": split_gold_paths,
        "approved_annotation_count": len(gold_rows),
        "split_counts": _split_counts(gold_rows),
    }


def validate_no_test_gold_in_runtime_registry(
    *,
    registry_rows: list[dict[str, Any]],
    expert_gold_rows: list[dict[str, Any]],
) -> None:
    test_gold_ids = {
        str(expert_gold_row.get("gold_id"))
        for expert_gold_row in expert_gold_rows
        if expert_gold_row.get("split") == AnnotationSplit.TEST.value
    }
    for registry_row in registry_rows:
        provenance_values = {
            str(registry_row.get("source") or ""),
            str(registry_row.get("source_id") or ""),
            str(registry_row.get("gold_id") or ""),
            str(registry_row.get("rationale") or ""),
        }
        if any(gold_id and gold_id in value for gold_id in test_gold_ids for value in provenance_values):
            raise ValueError(
                f"test gold leakage: registry row {registry_row.get('kind')}:{registry_row.get('value')} "
                "references an expert test gold record"
            )


def _annotation_to_expert_gold_row(annotation_record: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(annotation_record["doc_id"])
    gold_row: dict[str, Any] = {
        "gold_id": f"expert_gold_{doc_id}",
        "doc_id": doc_id,
        "split": annotation_record["split"],
        "gold_behavior": annotation_record["gold_behavior"],
        "created_for": EXPERT_OFFLINE_EVALUATION_ONLY,
        "frozen": True,
        "gold_source": EXPERT_GOLD_SOURCE,
        "source_card_hash": annotation_record["source_card_hash"],
        "annotation_id": annotation_record["annotation_id"],
        "annotator": annotation_record.get("annotator", ""),
    }
    optional_fields = (
        "condition",
        "nutrition_limits",
        "hard_exclusions",
        "preferred_tags",
        "expected_atomic_concepts",
        "alias_groups",
        "umbrella_relations",
        "extractability",
        "evidence_quotes",
        "review_notes",
    )
    for field_name in optional_fields:
        if field_name in annotation_record:
            gold_row[field_name] = annotation_record[field_name]
    return gold_row


def _validate_annotation_boundaries(annotation: dict[str, Any]) -> None:
    _require_enum_value(annotation, "split", AnnotationSplit)
    _require_enum_value(annotation, "annotation_status", AnnotationStatus)
    if not annotation.get("gold_behavior"):
        raise ValueError("expert annotation is missing gold_behavior")
    if not annotation.get("source_card_hash"):
        raise ValueError("expert annotation is missing source_card_hash")


def _require_enum_value(annotation: dict[str, Any], field_name: str, enum_type: type[Enum]) -> None:
    value = annotation.get(field_name)
    allowed_values = {member.value for member in enum_type}
    if value not in allowed_values:
        raise ValueError(f"{field_name} must be one of {sorted(allowed_values)}")


def _validate_source_hash(annotation: dict[str, Any], queue_record: dict[str, Any]) -> None:
    if annotation.get("source_card_hash") != queue_record.get("source_card_hash"):
        raise ValueError(f"stale source hash for {annotation.get('doc_id')}; reload source before saving")


def _validate_evidence_quotes(annotation: dict[str, Any], queue_record: dict[str, Any]) -> None:
    if annotation.get("paraphrased_evidence"):
        return
    source_text = str(queue_record.get("source_text") or "")
    for evidence_quote in annotation.get("evidence_quotes", []) or []:
        if evidence_quote and str(evidence_quote) not in source_text:
            raise ValueError(f"evidence quote is not present in source card for {annotation.get('doc_id')}")


def _resolve_source_card_path(dataset_dir: Path, manifest_row: dict[str, Any]) -> Path:
    source_card_path = manifest_row.get("source_card_path") or manifest_row.get("path")
    if not source_card_path:
        raise ValueError(f"manifest row {manifest_row.get('doc_id', '<unknown>')} is missing source path")
    raw_path = Path(str(source_card_path))
    if raw_path.is_absolute():
        return raw_path
    repo_root = dataset_dir.parent.parent.parent
    repo_relative_path = repo_root / raw_path
    if repo_relative_path.exists():
        return repo_relative_path
    return dataset_dir / raw_path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _split_counts(gold_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {split.value: 0 for split in AnnotationSplit}
    for gold_row in gold_rows:
        split = str(gold_row.get("split") or "")
        if split in counts:
            counts[split] += 1
    return {split: count for split, count in counts.items() if count}


def _write_split_gold_files(*, dataset_dir: Path, gold_rows: list[dict[str, Any]]) -> dict[str, str]:
    split_gold_paths: dict[str, str] = {}
    for split, file_name in EXPERT_GOLD_SPLIT_FILE_NAMES.items():
        split_path = dataset_dir / file_name
        split_rows = [gold_row for gold_row in gold_rows if gold_row.get("split") == split]
        _write_jsonl(split_path, split_rows)
        split_gold_paths[split] = str(split_path)
    return split_gold_paths
