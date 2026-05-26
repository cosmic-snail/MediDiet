from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from medidiet.llm import LLMResponse, LLMTask
from medidiet.rules import LimitScope, NutrientLimit, NutrientMetric
from knowledge.rule_extraction_dataset_smoke import (
    _limit_key,
    _rule_limit_key,
    build_chunking_report,
    run_real_llm_dataset_smoke,
    run_research_dry_run,
    run_research_real_run,
)


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


def test_build_chunking_report_has_strategy_summaries():
    report = build_chunking_report(REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1", REPO_ROOT / "knowledge" / "source_documents")
    assert "raw_card" in report["strategies"]
    assert "extractable_content" in report["strategies"]
    assert report["rows"]


def test_dry_run_generates_summary_reports(tmp_path: Path):
    run_research_dry_run("rule_extraction_v1", tmp_path, arms=["C2"], experiments=["E1"])
    assert (tmp_path / "doc-rule-agent-error-taxonomy.md").exists()
    assert (tmp_path / "doc-rule-agent-experiment-summary.md").exists()


class RecordingRuleLLMProvider:
    def __init__(self) -> None:
        self.tasks = []

    def complete(self, request):
        self.tasks.append(request.task)
        if request.task is LLMTask.RULE_EXTRACTION:
            return LLMResponse(
                content='{"rules":[{"condition":{"kind":"condition","value":"hypertension"},"hard_exclusions":[],"preferred_tags":[{"kind":"nutrition_tag","value":"low_sodium"}],"nutrition_limits":[{"metric":"sodium_mg","scope":"daily","max_value":2000,"window_hours":null}],"confidence":0.8,"evidence_quotes":{"nutrition_limits":"less than 2000 mg sodium per day"}}],"suggested_concepts":[]}',
                provider_name="recording",
                model="recording-model",
            )
        return LLMResponse(
            content='{"verdict":"pass","confidence":0.9,"consistency_score":0.9,"logic_score":0.9,"completeness_score":0.9,"issues":[],"missing_items":null,"evidence_quotes":{}}',
            provider_name="recording",
            model="recording-model",
        )


class FailingExtractionLLMProvider:
    def __init__(self) -> None:
        self.tasks = []

    def complete(self, request):
        self.tasks.append(request.task)
        raise RuntimeError("transport timeout")


def test_real_run_uses_llm_provider_and_writes_observation_report(tmp_path: Path):
    provider = RecordingRuleLLMProvider()
    result = run_research_real_run(
        "rule_extraction_v1",
        tmp_path,
        llm_provider=provider,
        arms=["C2"],
        experiments=["E1"],
        max_docs=1,
    )
    assert LLMTask.RULE_EXTRACTION in provider.tasks
    assert LLMTask.RULE_VALIDATION in provider.tasks
    assert result["observation_count"] == 1
    assert (tmp_path / "rule-extraction-v1-real-llm-report.json").exists()


def test_real_run_maps_c3_to_source_notes_plus_extractable(tmp_path: Path):
    provider = RecordingRuleLLMProvider()
    run_research_real_run(
        "rule_extraction_v1",
        tmp_path,
        llm_provider=provider,
        arms=["C3"],
        experiments=["E1"],
        max_docs=1,
    )
    report = __import__("json").loads(
        (tmp_path / "rule-extraction-v1-real-llm-report.json").read_text(encoding="utf-8")
    )
    assert report["observations"][0]["input_variant"] == "source_notes_plus_extractable"
    assert report["observations"][0]["observation_points"]["O5"]["input_variant"] == "source_notes_plus_extractable"


def test_real_run_excludes_api_failures_from_research_observations(tmp_path: Path):
    provider = FailingExtractionLLMProvider()
    observation_path = REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1" / "extraction_observations.jsonl"
    before = observation_path.read_text(encoding="utf-8")

    result = run_research_real_run(
        "rule_extraction_v1",
        tmp_path,
        llm_provider=provider,
        arms=["C2"],
        experiments=["E1"],
        max_docs=1,
        append_observations=True,
    )

    assert result["observation_count"] == 0
    assert result["operational_failure_count"] == 1
    assert observation_path.read_text(encoding="utf-8") == before

    report = __import__("json").loads(
        (tmp_path / "rule-extraction-v1-real-llm-report.json").read_text(encoding="utf-8")
    )
    assert report["observations"] == []
    assert report["operational_failures"][0]["excluded_from_research"] is True


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
