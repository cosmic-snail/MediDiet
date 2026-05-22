from __future__ import annotations

import json
from pathlib import Path

from knowledge.loader import KnowledgeLoader


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "knowledge" / "source_documents"
DATASET_DIR = REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1"


DATASET_FILES = {
    "README.zh.md",
    "manifest.jsonl",
    "expected_rules.jsonl",
    "extraction_observations.jsonl",
    "gold_evaluation_set.jsonl",
    "challenge_set.jsonl",
}


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{path}:{line_number} is invalid JSONL: {exc}") from exc
        assert isinstance(row, dict), f"{path}:{line_number} must contain a JSON object"
        rows.append(row)
    return rows


def test_dataset_skeleton_files_exist_and_jsonl_is_parseable():
    assert (SOURCE_ROOT / "manual").exists()
    assert DATASET_DIR.exists()
    for filename in DATASET_FILES:
        path = DATASET_DIR / filename
        assert path.exists(), f"missing dataset file: {path}"
        if path.suffix == ".jsonl":
            _read_jsonl(path)


def test_knowledge_loader_can_load_all_dataset_source_directories():
    loader = KnowledgeLoader()
    source_types = {
        "guidelines": "guideline",
        "papers": "paper",
        "manual": "manual",
    }
    for directory_name, source_type in source_types.items():
        docs = loader.load_from_directory(
            str(SOURCE_ROOT / directory_name),
            source_type=source_type,
        )
        assert isinstance(docs, list)


REQUIRED_MANIFEST_FIELDS = {
    "doc_id",
    "path",
    "title",
    "language",
    "source_type",
    "source_url",
    "publisher",
    "year",
    "disease_focus",
    "nutrition_focus",
    "evaluation_labels",
    "annotation_method",
    "label_model",
    "label_prompt_version",
    "label_confidence",
    "review_status",
    "failure_is_valid_observation",
    "copyright_mode",
    "notes",
}

ALLOWED_SOURCE_TYPES = {"guideline", "paper", "manual"}
ALLOWED_LANGUAGES = {"zh", "en"}
ALLOWED_EVALUATION_LABELS = {
    "should_extract",
    "concept_gap",
    "negative",
    "contextual",
    "conflict",
    "cross_language",
    "patient_education",
}


def _manifest_rows() -> list[dict]:
    return _read_jsonl(DATASET_DIR / "manifest.jsonl")


def test_guideline_manifest_subset_has_required_distribution():
    rows = _manifest_rows()
    guideline_rows = [row for row in rows if row.get("source_type") == "guideline"]
    assert len(guideline_rows) == 24
    assert sum(1 for row in guideline_rows if row["language"] == "zh") == 12
    assert sum(1 for row in guideline_rows if row["language"] == "en") == 12


def test_manifest_records_have_required_fields_and_existing_markdown_paths():
    rows = _manifest_rows()
    seen_doc_ids: set[str] = set()
    for row in rows:
        missing = REQUIRED_MANIFEST_FIELDS - set(row)
        assert not missing, f"{row.get('doc_id', 'unknown_doc')} missing fields: {sorted(missing)}"
        assert row["doc_id"] not in seen_doc_ids
        seen_doc_ids.add(row["doc_id"])
        assert row["language"] in ALLOWED_LANGUAGES
        assert row["source_type"] in ALLOWED_SOURCE_TYPES
        assert row["annotation_method"] == "llm_generated"
        assert row["review_status"] == "unreviewed"
        assert row["failure_is_valid_observation"] is True
        assert isinstance(row["label_confidence"], int | float)
        assert 0 <= row["label_confidence"] <= 1
        assert row["copyright_mode"] == "short_excerpt_or_summary"
        assert set(row["evaluation_labels"]).issubset(ALLOWED_EVALUATION_LABELS)
        path = REPO_ROOT / row["path"]
        assert path.exists(), f"source card path does not exist: {path}"
        assert path.suffix == ".md"
        text = path.read_text(encoding="utf-8")
        assert f"doc_id: {row['doc_id']}" in text
        assert f"source_url: \"{row['source_url']}\"" in text
        assert f"copyright_mode: {row['copyright_mode']}" in text
        assert f"notes: \"{row['notes']}\"" in text
