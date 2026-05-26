from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from knowledge.rule_extraction_dataset_smoke import (
    _limit_key,
    _rule_limit_key,
    build_chunking_report,
    run_real_llm_dataset_smoke,
)
from medidiet.rules import LimitScope, NutrientLimit, NutrientMetric


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1"
REPORT_DIR = Path(os.getenv("MEDIDIET_LLM_DATASET_REPORT_DIR", REPO_ROOT / "reports"))
REQUIRED_LLM_ENV = (
    "MEDIDIET_LLM_PROVIDER",
    "MEDIDIET_LLM_BASE_URL",
    "MEDIDIET_LLM_API_KEY",
    "MEDIDIET_LLM_MODEL",
)


def _dataset_smoke_enabled() -> bool:
    return os.getenv("MEDIDIET_LLM_DATASET_SMOKE_TEST") == "1" and all(
        os.getenv(name) for name in REQUIRED_LLM_ENV
    )


def test_rule_extraction_v1_gold_cards_write_chunking_report():
    report_path = REPORT_DIR / "rule-extraction-v1-chunking-report.json"

    report = build_chunking_report(
        repo_root=REPO_ROOT,
        dataset_dir=DATASET_DIR,
        report_path=report_path,
    )

    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["dataset"] == "rule_extraction_v1"
    assert report["gold_record_count"] == 14
    assert report["document_count"] == 14
    for document in report["documents"]:
        assert document["doc_id"]
        assert document["source_path"].endswith(".md")
        assert document["chunk_count"] >= 1
        assert document["chunks"]
        assert any("Extractable Source Content" in chunk["text_preview"] for chunk in document["chunks"])


def test_nutrition_limit_keys_keep_integer_values_readable():
    expected = {
        "metric": "sodium_mg",
        "scope": "daily",
        "max_value": 2000,
        "window_hours": None,
    }
    extracted = NutrientLimit(
        metric=NutrientMetric.SODIUM_MG,
        scope=LimitScope.DAILY,
        max_value=2000.0,
        window_hours=None,
    )

    assert _limit_key(expected) == "sodium_mg|daily|2000|None"
    assert _rule_limit_key(extracted) == "sodium_mg|daily|2000|None"


@pytest.mark.skipif(
    not _dataset_smoke_enabled(),
    reason="requires MEDIDIET_LLM_DATASET_SMOKE_TEST=1 and complete real LLM env vars",
)
def test_real_llm_rule_extraction_v1_gold_subset_writes_observation_report():
    report_path = REPORT_DIR / "rule-extraction-v1-real-llm-report.json"

    report = run_real_llm_dataset_smoke(
        repo_root=REPO_ROOT,
        dataset_dir=DATASET_DIR,
        report_path=report_path,
        limit=5,
    )

    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["dataset"] == "rule_extraction_v1"
    assert report["mode"] == "real_llm_dataset_smoke"
    assert len(report["observations"]) == 5
    for observation in report["observations"]:
        assert observation["doc_id"]
        assert observation["gold_id"]
        assert observation["chunks"]
        assert "rules" in observation
        assert "suggested_concepts" in observation
        assert "field_match" in observation
