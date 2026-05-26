from __future__ import annotations

import json
from pathlib import Path

from knowledge.extraction_observations import ExtractionObservation, append_observation


def test_append_observation_writes_valid_jsonl(tmp_path: Path):
    path = tmp_path / "observations.jsonl"
    observation = ExtractionObservation(run_id="run-test", experiment_id="E1", arm_id="C2", dataset_id="rule_extraction_v1", doc_id="en_guideline_who_sodium_2012", expected_id="exp-test", gold_id="gold-test", input_variant="extractable_content", extractor_name="current_two_stage", model="deepseek-chat", provider="deepseek", temperature=0.0, prompt_version="rule-extractor-v1", prompt_hash="sha256:prompt", input_hash="sha256:input", source_card_hash="sha256:source", chunk_hashes=["sha256:chunk"], latency_ms=1200, retry_count=1, finish_reason="stop", raw_output_hash="sha256:raw", raw_output_path="reports/raw/run-test.json", parse_status="parsed", parsed_rules=[], suggested_concepts=[], observation_points={"O6": {"empty_output": False}, "O10": {"overall": "miss"}}, evaluator={"field_match": False}, failures=["missing_numeric_limit"])
    append_observation(path, observation)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["run_id"] == "run-test"
    assert rows[0]["experiment_id"] == "E1"
    assert rows[0]["arm_id"] == "C2"
    assert rows[0]["observation_points"]["O6"]["empty_output"] is False
    assert rows[0]["failures"] == ["missing_numeric_limit"]
    assert rows[0]["parsed_rules"] == []
