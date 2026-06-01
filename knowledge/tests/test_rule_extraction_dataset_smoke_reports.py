from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from medidiet.llm import LLMResponse, LLMTask
from medidiet.rules import LimitScope, NutrientLimit, NutrientMetric
import knowledge.rule_extraction_dataset_smoke as smoke
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


class RecordingAcceptJudgeProvider:
    def __init__(self) -> None:
        self.tasks = []
        self.requests = []

    def complete(self, request):
        self.tasks.append(request.task)
        self.requests.append(request)
        return LLMResponse(
            content='{"verdict":"accept","confidence":0.85,"field_verdicts":{"condition":"accept","nutrition_limits":"accept"},"reason":"supported"}',
            provider_name="judge",
            model="judge-model",
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
    assert result["evaluated_record_count"] == 1
    assert (tmp_path / "rule-extraction-v1-real-llm-report.json").exists()
    assert (tmp_path / "rule-extraction-v1-real-llm-field-evaluation-report.json").exists()
    assert (tmp_path / "rule-extraction-v1-real-llm-summary.md").exists()
    assert (tmp_path / "rule-extraction-v1-golden-eval-accuracy-report.json").exists()
    assert (tmp_path / "rule-extraction-v1-golden-eval-accuracy-chart.png").exists()
    assert result["golden_eval_accuracy_chart_path"].endswith("rule-extraction-v1-golden-eval-accuracy-chart.png")
    report = json.loads((tmp_path / "rule-extraction-v1-real-llm-report.json").read_text(encoding="utf-8"))
    assert report["evaluation_summary"]["evaluated_record_count"] == 1
    assert report["golden_eval_accuracy"]["chart_path"].endswith("rule-extraction-v1-golden-eval-accuracy-chart.png")
    assert report["layer_0_plausibility"]["pass"] == 1
    assert report["layer_1_grounding"]["evaluated_observation_count"] == 1
    assert "plausibility" in report["observations"][0]["evaluator"]
    assert "grounding" in report["observations"][0]["evaluator"]
    assert report["evaluations"][0]["gold_id"] == "gold_zh_guideline_hypertension_food_therapy_2023_001"
    assert report["evaluations"][0]["arm_id"] == "C2"


def test_real_run_can_include_layer_2_judge_summary(tmp_path: Path):
    extractor_provider = RecordingRuleLLMProvider()
    judge_provider = RecordingAcceptJudgeProvider()

    run_research_real_run(
        "rule_extraction_v1",
        tmp_path,
        llm_provider=extractor_provider,
        judge_provider=judge_provider,
        arms=["C2"],
        experiments=["E1"],
        max_docs=1,
    )

    report = json.loads((tmp_path / "rule-extraction-v1-real-llm-report.json").read_text(encoding="utf-8"))
    accuracy_report = json.loads((tmp_path / "rule-extraction-v1-golden-eval-accuracy-report.json").read_text(encoding="utf-8"))
    assert LLMTask.RULE_VALIDATION in judge_provider.tasks
    assert report["layer_2_judge"]["evaluated_rule_count"] == 1
    assert report["layer_2_judge"]["accept_rate"] == 1.0
    assert report["layer_2_judge"]["calibration"]["calibrated_record_count"] == 1
    assert "judge" in report["observations"][0]["evaluator"]
    assert accuracy_report["layer_2_judge"]["accept_rate"] == 1.0
    assert (tmp_path / "rule-extraction-v1-layered-evaluation-summary.md").exists()


def test_real_run_passes_gold_expectation_to_layer_2_judge(tmp_path: Path):
    extractor_provider = RecordingRuleLLMProvider()
    judge_provider = RecordingAcceptJudgeProvider()

    run_research_real_run(
        "rule_extraction_v1",
        tmp_path,
        llm_provider=extractor_provider,
        judge_provider=judge_provider,
        arms=["C2"],
        experiments=["E1"],
        max_docs=1,
    )

    prompt_payload = json.loads(judge_provider.requests[0].user_prompt)
    expected_gold_rule = prompt_payload["evaluation_context"]["expected_gold_rule"]
    assert expected_gold_rule["gold_id"] == "gold_zh_guideline_hypertension_food_therapy_2023_001"
    assert expected_gold_rule["nutrition_limits"][0]["metric"] == "sodium_mg"
    assert "missing required nutrition_limits" in judge_provider.requests[0].system_prompt


def test_real_run_limits_layer_2_judge_rule_count(tmp_path: Path):
    extractor_provider = RecordingRuleLLMProvider()
    judge_provider = RecordingAcceptJudgeProvider()

    run_research_real_run(
        "rule_extraction_v1",
        tmp_path,
        llm_provider=extractor_provider,
        judge_provider=judge_provider,
        judge_max_rules=0,
        arms=["C2"],
        experiments=["E1"],
        max_docs=1,
    )

    report = json.loads((tmp_path / "rule-extraction-v1-real-llm-report.json").read_text(encoding="utf-8"))
    assert judge_provider.tasks == []
    assert report["layer_2_judge"]["evaluated_rule_count"] == 0


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
    assert report["observations"][0]["source_content_strategy"] == "source_notes_plus_extractable"
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


def test_cli_exposes_real_llm_max_docs_and_judge_controls(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_real_run(
        dataset,
        output_dir,
        llm_provider=None,
        judge_provider=None,
        judge_max_rules=None,
        arms=None,
        experiments=None,
        max_docs=None,
        max_empty_retries=2,
        inter_doc_delay_seconds=5.0,
        append_observations=False,
    ):
        captured.update(
            {
                "dataset": dataset,
                "output_dir": output_dir,
                "arms": arms,
                "experiments": experiments,
                "max_docs": max_docs,
                "max_empty_retries": max_empty_retries,
                "inter_doc_delay_seconds": inter_doc_delay_seconds,
                "append_observations": append_observations,
                "judge_provider": judge_provider,
                "judge_max_rules": judge_max_rules,
            }
        )
        return {}

    monkeypatch.setattr(smoke, "run_research_real_run", fake_real_run)
    monkeypatch.setattr(smoke, "OpenAICompatibleLLMProvider", lambda config: "judge-provider")

    result = smoke.main(
        [
            "--real-llm",
            "--dataset",
            "rule_extraction_v1",
            "--output-dir",
            str(tmp_path),
            "--experiments",
            "E1",
            "--arms",
            "C1,C2",
            "--max-docs",
            "5",
            "--judge-llm",
            "--judge-max-rules",
            "7",
            "--max-empty-retries",
            "3",
            "--inter-doc-delay-seconds",
            "1.5",
            "--append-observations",
        ]
    )

    assert result == 0
    assert captured["max_docs"] == 5
    assert captured["append_observations"] is True
    assert captured["arms"] == ["C1", "C2"]
    assert captured["experiments"] == ["E1"]
    assert captured["max_empty_retries"] == 3
    assert captured["inter_doc_delay_seconds"] == 1.5
    assert captured["judge_provider"] == "judge-provider"
    assert captured["judge_max_rules"] == 7


def test_cli_real_llm_defaults_to_all_docs_and_keeps_rate_limit_delay(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_real_run(dataset, output_dir, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(smoke, "run_research_real_run", fake_real_run)

    result = smoke.main(["--real-llm", "--output-dir", str(tmp_path)])

    assert result == 0
    assert captured["max_docs"] is None
    assert captured["max_empty_retries"] == 2
    assert captured["inter_doc_delay_seconds"] == 5.0


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
