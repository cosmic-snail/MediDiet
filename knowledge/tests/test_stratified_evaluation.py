from pathlib import Path

from knowledge.stratified_evaluation import build_stratified_evaluation_report, load_track_expectations


def test_stratified_report_exposes_track_summaries_without_averaging_them():
    gold_rows = [
        {"gold_id": "gold-clean", "doc_id": "clean-doc", "gold_behavior": "rule"},
        {"gold_id": "gold-concept", "doc_id": "concept-doc", "gold_behavior": "suggested_concept"},
    ]
    audit_rows = [
        {"gold_id": "gold-clean", "evidence_level": "source_card_direct", "audit_status": "keep"},
        {"gold_id": "gold-concept", "evidence_level": "schema_gap", "audit_status": "revise_schema_or_gold"},
    ]
    rule_evaluations = [
        {"gold_id": "gold-clean", "experiment_id": "E1", "arm_id": "C2", "overall": "match"},
        {"gold_id": "gold-concept", "experiment_id": "E1", "arm_id": "C2", "overall": "miss"},
    ]
    concept_evaluations = [
        {
            "gold_id": "gold-concept",
            "doc_id": "concept-doc",
            "overall": "match",
            "raw_suggested_concepts": [{"kind": "nutrition_tag", "value": "low_purine"}],
            "matched_concepts": [{"kind": "nutrition_tag", "value": "low_purine"}],
            "missing_concepts": [],
            "extra_concepts": [],
            "true_positive_count": 2,
            "false_negative_count": 0,
            "false_positive_count": 0,
        }
    ]

    report = build_stratified_evaluation_report(
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        gold_rows=gold_rows,
        audit_rows=audit_rows,
        rule_evaluations=rule_evaluations,
        concept_evaluations=concept_evaluations,
        conversion_evaluations=[],
        contextual_evaluations=[],
    )

    assert report["headline_metric"] == "clean_extraction_f1"
    assert report["tracks"]["clean_extraction"]["overall"]["f1"] == 1.0
    assert report["tracks"]["concept_discovery"]["overall"]["atomic"]["f1"] == 1.0
    assert report["tracks"]["concept_discovery"]["records"] == concept_evaluations
    assert report["tracks"]["mixed_legacy"]["overall"]["recall"] < 1.0


def test_load_track_expectations_reads_all_track_files(tmp_path: Path):
    dataset_dir = tmp_path
    (dataset_dir / "concept_expectations.jsonl").write_text('{"gold_id":"gold-concept"}\n', encoding="utf-8")
    (dataset_dir / "conversion_expectations.jsonl").write_text('{"gold_id":"gold-conversion"}\n', encoding="utf-8")
    (dataset_dir / "contextual_expectations.jsonl").write_text('{"gold_id":"gold-contextual"}\n', encoding="utf-8")

    expectations = load_track_expectations(dataset_dir)

    assert expectations["concept_discovery"][0]["gold_id"] == "gold-concept"
    assert expectations["conversion"][0]["gold_id"] == "gold-conversion"
    assert expectations["contextual_handling"][0]["gold_id"] == "gold-contextual"
