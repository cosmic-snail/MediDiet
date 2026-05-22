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
