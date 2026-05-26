from __future__ import annotations

from pathlib import Path

from medidiet.llm import LLMResponse, LLMTask
from knowledge.rule_extraction_dataset_smoke import build_chunking_report, run_research_dry_run
from knowledge.rule_extraction_dataset_smoke import run_research_real_run


REPO_ROOT = Path(__file__).resolve().parents[2]


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
