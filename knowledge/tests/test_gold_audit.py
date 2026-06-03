from __future__ import annotations

from pathlib import Path

from knowledge.gold_audit import (
    annotate_evaluations_with_gold_audit,
    build_gold_audit_report,
    write_gold_audit_report,
)


def test_gold_audit_report_filters_clean_headline_rows():
    gold_rows = [
        {"gold_id": "gold-direct", "doc_id": "direct-doc", "gold_behavior": "rule"},
        {"gold_id": "gold-derived", "doc_id": "derived-doc", "gold_behavior": "rule"},
        {"gold_id": "gold-schema", "doc_id": "schema-doc", "gold_behavior": "suggested_concept"},
    ]
    audit_rows = [
        {
            "gold_id": "gold-direct",
            "evidence_level": "source_card_direct",
            "audit_status": "keep",
            "recommended_action": "keep",
        },
        {
            "gold_id": "gold-derived",
            "evidence_level": "derived_conversion",
            "audit_status": "revise_gold",
            "recommended_action": "remove_numeric_limit",
        },
        {
            "gold_id": "gold-schema",
            "evidence_level": "schema_gap",
            "audit_status": "revise_schema_or_gold",
            "recommended_action": "replace_umbrella_concept",
        },
    ]
    evaluations = [
        {"gold_id": "gold-direct", "experiment_id": "E1", "arm_id": "C2", "overall": "match"},
        {"gold_id": "gold-derived", "experiment_id": "E1", "arm_id": "C2", "overall": "miss"},
        {"gold_id": "gold-schema", "experiment_id": "E1", "arm_id": "C2", "overall": "miss"},
    ]

    report = build_gold_audit_report(
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        gold_rows=gold_rows,
        evaluations=evaluations,
        audit_rows=audit_rows,
    )

    assert report["summary"]["gold_record_count"] == 3
    assert report["summary"]["clean_headline_record_count"] == 1
    assert report["summary"]["audit_status_counts"] == {
        "keep": 1,
        "revise_gold": 1,
        "revise_schema_or_gold": 1,
    }
    assert report["clean_evaluation_summary"]["overall"] == {
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert report["all_evaluation_summary"]["overall"]["recall"] < 1.0


def test_gold_audit_report_keeps_trusted_contextual_negatives_in_clean_headline():
    gold_rows = [
        {"gold_id": "gold-direct", "doc_id": "direct-doc", "gold_behavior": "rule"},
        {"gold_id": "gold-negative", "doc_id": "negative-doc", "gold_behavior": "negative"},
    ]
    audit_rows = [
        {
            "gold_id": "gold-direct",
            "evidence_level": "source_card_direct",
            "audit_status": "keep",
            "recommended_action": "keep",
        },
        {
            "gold_id": "gold-negative",
            "evidence_level": "contextual_negative",
            "audit_status": "keep",
            "recommended_action": "keep",
        },
    ]
    evaluations = [
        {"gold_id": "gold-direct", "experiment_id": "E1", "arm_id": "C2", "overall": "match"},
        {
            "gold_id": "gold-negative",
            "experiment_id": "E1",
            "arm_id": "C2",
            "overall": "mismatch",
            "failures": ["unexpected_numeric_limit"],
        },
    ]

    report = build_gold_audit_report(
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        gold_rows=gold_rows,
        evaluations=evaluations,
        audit_rows=audit_rows,
    )

    assert report["summary"]["clean_headline_record_count"] == 2
    assert report["clean_evaluation_summary"]["evaluated_record_count"] == 2
    assert report["clean_evaluation_summary"]["overall"]["precision"] == 0.5


def test_annotate_evaluations_with_gold_audit_preserves_recommendations():
    evaluations = [{"gold_id": "gold-direct", "overall": "match"}]
    audit_rows = [
        {
            "gold_id": "gold-direct",
            "evidence_level": "original_source_direct",
            "audit_status": "keep",
            "recommended_action": "keep",
            "audit_notes": "direct source evidence",
        }
    ]

    annotated = annotate_evaluations_with_gold_audit(evaluations, audit_rows)

    assert annotated[0]["evidence_level"] == "original_source_direct"
    assert annotated[0]["audit_status"] == "keep"
    assert annotated[0]["recommended_action"] == "keep"
    assert annotated[0]["audit_notes"] == "direct source evidence"


def test_gold_audit_artifact_path_is_stable():
    assert Path("knowledge/datasets/rule_extraction_v1/gold_audit.jsonl").suffix == ".jsonl"


def test_write_gold_audit_report_returns_same_report_it_writes(tmp_path: Path):
    gold_rows = [{"gold_id": "gold-direct", "doc_id": "direct-doc", "gold_behavior": "rule"}]
    audit_rows = [
        {
            "gold_id": "gold-direct",
            "evidence_level": "source_card_direct",
            "audit_status": "keep",
            "recommended_action": "keep",
        }
    ]
    evaluations = [{"gold_id": "gold-direct", "experiment_id": "E1", "arm_id": "C2", "overall": "match"}]

    report = write_gold_audit_report(
        output_dir=tmp_path,
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        gold_rows=gold_rows,
        evaluations=evaluations,
        audit_rows=audit_rows,
    )

    report_path = Path(report["report_path"])
    assert report["clean_evaluation_summary"]["overall"]["f1"] == 1.0
    assert report_path.exists()
    assert '"clean_evaluation_summary"' in report_path.read_text(encoding="utf-8")
