from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.rule_evaluation import precision_recall_f1


CLEAN_HEADLINE_EVIDENCE_LEVELS = {"source_card_direct", "original_source_direct", "contextual_negative"}
CLEAN_HEADLINE_AUDIT_STATUSES = {"keep"}


def load_gold_audit_rows(dataset_dir: Path) -> list[dict[str, Any]]:
    audit_path = dataset_dir / "gold_audit.jsonl"
    if not audit_path.exists():
        return []
    gold_audit_rows: list[dict[str, Any]] = []
    for raw_line in audit_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            gold_audit_rows.append(json.loads(line))
    return gold_audit_rows


def annotate_evaluations_with_gold_audit(
    evaluations: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gold_audit_by_gold_id = {
        str(gold_audit_row.get("gold_id")): gold_audit_row for gold_audit_row in audit_rows
    }
    annotated_evaluations: list[dict[str, Any]] = []
    for evaluation in evaluations:
        gold_audit_row = gold_audit_by_gold_id.get(str(evaluation.get("gold_id")))
        if not gold_audit_row:
            annotated_evaluations.append(dict(evaluation))
            continue
        annotated_evaluations.append(
            {
                **evaluation,
                "evidence_level": gold_audit_row.get("evidence_level"),
                "audit_status": gold_audit_row.get("audit_status"),
                "recommended_action": gold_audit_row.get("recommended_action"),
                "audit_notes": gold_audit_row.get("audit_notes", ""),
            }
        )
    return annotated_evaluations


def build_gold_audit_report(
    *,
    dataset_id: str,
    run_type: str,
    gold_rows: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_audit_by_gold_id = {
        str(gold_audit_row.get("gold_id")): gold_audit_row for gold_audit_row in audit_rows
    }
    annotated_evaluations = annotate_evaluations_with_gold_audit(evaluations, audit_rows)
    clean_evaluations = [
        evaluation
        for evaluation in annotated_evaluations
        if evaluation.get("evidence_level") in CLEAN_HEADLINE_EVIDENCE_LEVELS
        and evaluation.get("audit_status") in CLEAN_HEADLINE_AUDIT_STATUSES
    ]
    audit_status_counts = Counter(str(gold_audit_row.get("audit_status") or "missing") for gold_audit_row in audit_rows)
    evidence_level_counts = Counter(
        str(gold_audit_row.get("evidence_level") or "missing") for gold_audit_row in audit_rows
    )

    return {
        "dataset_id": dataset_id,
        "run_type": run_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "gold_record_count": len(gold_rows),
            "audit_record_count": len(audit_rows),
            "audit_coverage_count": sum(
                1
                for gold_evaluation_row in gold_rows
                if str(gold_evaluation_row.get("gold_id")) in gold_audit_by_gold_id
            ),
            "clean_headline_record_count": len(
                [
                    gold_audit_row
                    for gold_audit_row in audit_rows
                    if gold_audit_row.get("evidence_level") in CLEAN_HEADLINE_EVIDENCE_LEVELS
                    and gold_audit_row.get("audit_status") in CLEAN_HEADLINE_AUDIT_STATUSES
                ]
            ),
            "audit_status_counts": dict(sorted(audit_status_counts.items())),
            "evidence_level_counts": dict(sorted(evidence_level_counts.items())),
        },
        "all_evaluation_summary": _summarize_evaluations(annotated_evaluations),
        "clean_evaluation_summary": _summarize_evaluations(clean_evaluations),
        "rows": [
            {
                **gold_evaluation_row,
                **{
                    key: value
                    for key, value in gold_audit_by_gold_id.get(str(gold_evaluation_row.get("gold_id")), {}).items()
                    if key != "gold_id"
                },
            }
            for gold_evaluation_row in gold_rows
        ],
    }


def write_gold_audit_report(
    *,
    output_dir: Path,
    dataset_id: str,
    run_type: str,
    gold_rows: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    report_filename: str = "rule-extraction-v1-gold-audit-report.json",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_gold_audit_report(
        dataset_id=dataset_id,
        run_type=run_type,
        gold_rows=gold_rows,
        evaluations=evaluations,
        audit_rows=audit_rows,
    )
    report_path = output_dir / report_filename
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**report, "report_path": str(report_path)}


def _summarize_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for evaluation in evaluations:
        key = (str(evaluation.get("experiment_id", "")), str(evaluation.get("arm_id", "")))
        grouped.setdefault(key, []).append(evaluation)
    return {
        "evaluated_record_count": len(evaluations),
        "overall": precision_recall_f1(evaluations),
        "by_experiment_arm": [
            {
                "experiment_id": experiment_id,
                "arm_id": arm_id,
                "evaluated_record_count": len(rows),
                **precision_recall_f1(rows),
            }
            for (experiment_id, arm_id), rows in sorted(grouped.items())
        ],
    }
