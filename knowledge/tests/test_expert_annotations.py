from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowledge.expert_annotation_app import create_expert_annotation_app
from knowledge.expert_annotations import (
    AnnotationSplit,
    AnnotationStatus,
    append_expert_annotation,
    build_annotation_queue,
    freeze_expert_gold_annotations,
    latest_annotations_by_doc_id,
    validate_no_test_gold_in_runtime_registry,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sample_dataset(tmp_path: Path) -> Path:
    dataset_dir = tmp_path / "rule_extraction_v1"
    source_dir = tmp_path / "source_documents"
    dataset_dir.mkdir()
    source_dir.mkdir()
    (source_dir / "doc-a.md").write_text(
        "---\ndoc_id: doc-a\n---\n\n## Extractable Source Content\nAdults should reduce sodium intake.\n",
        encoding="utf-8",
    )
    (source_dir / "doc-b.md").write_text(
        "---\ndoc_id: doc-b\n---\n\n## Extractable Source Content\nThis is broad education without a fixed nutrient limit.\n",
        encoding="utf-8",
    )
    _write_jsonl(
        dataset_dir / "manifest.jsonl",
        [
            {
                "doc_id": "doc-a",
                "path": str(source_dir / "doc-a.md"),
                "title": "Doc A",
                "language": "en",
                "source_type": "guideline",
            },
            {
                "doc_id": "doc-b",
                "path": str(source_dir / "doc-b.md"),
                "title": "Doc B",
                "language": "en",
                "source_type": "manual",
            },
        ],
    )
    _write_jsonl(
        dataset_dir / "expected_rules.jsonl",
        [
            {
                "doc_id": "doc-a",
                "expected_behavior": "rule",
                "condition": {"kind": "condition", "value": "hypertension"},
                "preferred_tags": [{"kind": "nutrition_tag", "value": "low_sodium"}],
                "review_status": "unreviewed",
            }
        ],
    )
    return dataset_dir


def test_annotation_queue_shows_source_and_silver_labels_without_marking_reviewed(tmp_path: Path):
    dataset_dir = _sample_dataset(tmp_path)

    queue = build_annotation_queue(dataset_dir)

    assert queue[0]["doc_id"] == "doc-a"
    assert "Adults should reduce sodium" in queue[0]["source_text"]
    assert queue[0]["source_card_hash"].startswith("sha256:")
    assert queue[0]["latest_annotation"] is None
    assert queue[0]["silver_expected"]["expected_behavior"] == "rule"


def test_append_expert_annotation_keeps_audit_history_and_latest_record(tmp_path: Path):
    dataset_dir = _sample_dataset(tmp_path)
    queue_record = build_annotation_queue(dataset_dir)[0]

    first_record = append_expert_annotation(
        dataset_dir=dataset_dir,
        annotation={
            "doc_id": "doc-a",
            "split": AnnotationSplit.DEV.value,
            "annotation_status": AnnotationStatus.NEEDS_REVISION.value,
            "source_card_hash": queue_record["source_card_hash"],
            "gold_behavior": "suggested_concept",
            "annotator": "expert-a",
            "evidence_quotes": ["Adults should reduce sodium intake."],
        },
    )
    second_record = append_expert_annotation(
        dataset_dir=dataset_dir,
        annotation={
            "doc_id": "doc-a",
            "split": AnnotationSplit.TEST.value,
            "annotation_status": AnnotationStatus.APPROVED.value,
            "source_card_hash": queue_record["source_card_hash"],
            "gold_behavior": "rule",
            "annotator": "expert-a",
            "condition": {"kind": "condition", "value": "hypertension"},
            "expected_atomic_concepts": [
                {"kind": "nutrition_tag", "value": "low_sodium", "aliases": ["sodium reduction"]}
            ],
            "evidence_quotes": ["Adults should reduce sodium intake."],
        },
    )

    audit_rows = _read_jsonl(dataset_dir / "expert_annotations.jsonl")
    latest = latest_annotations_by_doc_id(dataset_dir)

    assert first_record["annotation_id"] != second_record["annotation_id"]
    assert len(audit_rows) == 2
    assert latest["doc-a"]["split"] == AnnotationSplit.TEST.value
    assert latest["doc-a"]["annotation_status"] == AnnotationStatus.APPROVED.value


def test_freeze_expert_gold_uses_only_approved_latest_rows_and_preserves_split(tmp_path: Path):
    dataset_dir = _sample_dataset(tmp_path)
    queue_records = {record["doc_id"]: record for record in build_annotation_queue(dataset_dir)}
    append_expert_annotation(
        dataset_dir=dataset_dir,
        annotation={
            "doc_id": "doc-a",
            "split": AnnotationSplit.TEST.value,
            "annotation_status": AnnotationStatus.APPROVED.value,
            "source_card_hash": queue_records["doc-a"]["source_card_hash"],
            "gold_behavior": "rule",
            "annotator": "expert-a",
            "condition": {"kind": "condition", "value": "hypertension"},
            "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000}],
            "evidence_quotes": ["Adults should reduce sodium intake."],
        },
    )
    append_expert_annotation(
        dataset_dir=dataset_dir,
        annotation={
            "doc_id": "doc-b",
            "split": AnnotationSplit.TRAIN.value,
            "annotation_status": AnnotationStatus.NEEDS_REVISION.value,
            "source_card_hash": queue_records["doc-b"]["source_card_hash"],
            "gold_behavior": "negative",
            "annotator": "expert-a",
        },
    )

    result = freeze_expert_gold_annotations(dataset_dir=dataset_dir)

    gold_rows = _read_jsonl(Path(result["gold_path"]))
    assert result["approved_annotation_count"] == 1
    assert gold_rows == [
        {
            "annotation_id": gold_rows[0]["annotation_id"],
            "annotator": "expert-a",
            "created_for": "expert_offline_evaluation_only",
            "condition": {"kind": "condition", "value": "hypertension"},
            "doc_id": "doc-a",
            "evidence_quotes": ["Adults should reduce sodium intake."],
            "frozen": True,
            "gold_behavior": "rule",
            "gold_id": "expert_gold_doc-a",
            "gold_source": "expert_annotation",
            "nutrition_limits": [{"max_value": 2000, "metric": "sodium_mg", "scope": "daily"}],
            "source_card_hash": queue_records["doc-a"]["source_card_hash"],
            "split": AnnotationSplit.TEST.value,
        }
    ]
    assert Path(result["split_gold_paths"][AnnotationSplit.TEST.value]).exists()
    assert _read_jsonl(Path(result["split_gold_paths"][AnnotationSplit.TEST.value])) == gold_rows


def test_freeze_rejects_stale_source_hash(tmp_path: Path):
    dataset_dir = _sample_dataset(tmp_path)
    queue_record = build_annotation_queue(dataset_dir)[0]
    append_expert_annotation(
        dataset_dir=dataset_dir,
        annotation={
            "doc_id": "doc-a",
            "split": AnnotationSplit.DEV.value,
            "annotation_status": AnnotationStatus.APPROVED.value,
            "source_card_hash": queue_record["source_card_hash"],
            "gold_behavior": "rule",
            "annotator": "expert-a",
        },
    )
    source_path = Path(build_annotation_queue(dataset_dir)[0]["source_card_path"])
    source_path.write_text(source_path.read_text(encoding="utf-8") + "\nChanged after review.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="stale source hash"):
        freeze_expert_gold_annotations(dataset_dir=dataset_dir)


def test_leakage_guard_rejects_test_gold_as_runtime_registry_source():
    registry_rows = [
        {
            "kind": "nutrition_tag",
            "value": "low_sodium",
            "source": "expert_gold_doc-a",
            "status": "approved_for_research",
        }
    ]
    expert_gold_rows = [
        {
            "gold_id": "expert_gold_doc-a",
            "split": AnnotationSplit.TEST.value,
            "expected_atomic_concepts": [{"kind": "nutrition_tag", "value": "low_sodium"}],
        }
    ]

    with pytest.raises(ValueError, match="test gold leakage"):
        validate_no_test_gold_in_runtime_registry(
            registry_rows=registry_rows,
            expert_gold_rows=expert_gold_rows,
        )


def test_annotation_app_saves_annotations_and_freezes_gold(tmp_path: Path):
    dataset_dir = _sample_dataset(tmp_path)
    client = TestClient(create_expert_annotation_app(dataset_dir=dataset_dir))
    queue_response = client.get("/api/queue")
    queue_response.raise_for_status()
    queue_record = queue_response.json()["records"][0]

    save_response = client.post(
        "/api/annotations",
        json={
            "doc_id": "doc-a",
            "split": AnnotationSplit.DEV.value,
            "annotation_status": AnnotationStatus.APPROVED.value,
            "source_card_hash": queue_record["source_card_hash"],
            "gold_behavior": "rule",
            "annotator": "expert-a",
            "evidence_quotes": ["Adults should reduce sodium intake."],
        },
    )
    save_response.raise_for_status()
    freeze_response = client.post("/api/freeze")
    freeze_response.raise_for_status()

    assert save_response.json()["record"]["annotation_status"] == AnnotationStatus.APPROVED.value
    assert freeze_response.json()["approved_annotation_count"] == 1
    assert Path(freeze_response.json()["gold_path"]).exists()
