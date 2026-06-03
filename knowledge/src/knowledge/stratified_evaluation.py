from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.concept_evaluation import summarize_concept_evaluations
from knowledge.evaluation_taxonomy import EvaluationTrack, clean_headline_filter
from knowledge.gold_audit import annotate_evaluations_with_gold_audit, build_gold_audit_report
from knowledge.rule_evaluation import precision_recall_f1


TRACK_EXPECTATION_FILES = {
    EvaluationTrack.CONCEPT_DISCOVERY.value: "concept_expectations.jsonl",
    EvaluationTrack.CONVERSION.value: "conversion_expectations.jsonl",
    EvaluationTrack.CONTEXTUAL_HANDLING.value: "contextual_expectations.jsonl",
}


def load_track_expectations(dataset_dir: Path) -> dict[str, list[dict[str, Any]]]:
    expectations_by_track: dict[str, list[dict[str, Any]]] = {}
    for evaluation_track, filename in TRACK_EXPECTATION_FILES.items():
        expectation_path = dataset_dir / filename
        expectations_by_track[evaluation_track] = _read_jsonl(expectation_path)
    return expectations_by_track


def build_stratified_evaluation_report(
    *,
    dataset_id: str,
    run_type: str,
    gold_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    rule_evaluations: list[dict[str, Any]],
    concept_evaluations: list[dict[str, Any]],
    conversion_evaluations: list[dict[str, Any]],
    contextual_evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_audit_report = build_gold_audit_report(
        dataset_id=dataset_id,
        run_type=run_type,
        gold_rows=gold_rows,
        evaluations=rule_evaluations,
        audit_rows=audit_rows,
    )
    annotated_rule_evaluations = annotate_evaluations_with_gold_audit(rule_evaluations, audit_rows)
    clean_rule_evaluations = [
        rule_evaluation
        for rule_evaluation in annotated_rule_evaluations
        if rule_evaluation.get("gold_id")
        and rule_evaluation.get("evidence_level") is not None
        and rule_evaluation.get("audit_status") is not None
        and clean_headline_filter(
            evidence_level=str(rule_evaluation["evidence_level"]),
            audit_status=str(rule_evaluation["audit_status"]),
        )
    ]
    return {
        "dataset_id": dataset_id,
        "run_type": run_type,
        "headline_metric": "clean_extraction_f1",
        "tracks": {
            EvaluationTrack.CLEAN_EXTRACTION.value: {
                "evaluated_record_count": len(clean_rule_evaluations),
                "overall": precision_recall_f1(clean_rule_evaluations),
            },
            EvaluationTrack.CONCEPT_DISCOVERY.value: {
                "evaluated_record_count": len(concept_evaluations),
                "overall": summarize_concept_evaluations(concept_evaluations),
                "records": concept_evaluations,
            },
            EvaluationTrack.CONVERSION.value: {
                "evaluated_record_count": len(conversion_evaluations),
                "overall": _binary_accuracy(conversion_evaluations),
            },
            EvaluationTrack.CONTEXTUAL_HANDLING.value: {
                "evaluated_record_count": len(contextual_evaluations),
                "overall": _binary_accuracy(contextual_evaluations),
            },
            EvaluationTrack.MIXED_LEGACY.value: gold_audit_report["all_evaluation_summary"],
        },
        "gold_audit": gold_audit_report,
    }


def _binary_accuracy(evaluations: list[dict[str, Any]]) -> dict[str, float]:
    if not evaluations:
        return {"accuracy": 0.0}
    matches = sum(1 for evaluation in evaluations if evaluation.get("overall") == "match")
    return {"accuracy": matches / len(evaluations)}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
