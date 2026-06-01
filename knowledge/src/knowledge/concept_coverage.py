from __future__ import annotations

from collections import Counter
from typing import Any

from medidiet.domain import CodeKind, ConceptRegistry


def audit_concept_coverage(
    *,
    manifest_rows: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    registry: ConceptRegistry,
) -> dict[str, Any]:
    focus_counts, focus_doc_ids = _count_manifest_condition_focus(manifest_rows)
    registered_focus: dict[str, dict[str, Any]] = {}
    missing_focus: dict[str, dict[str, Any]] = {}
    for condition_focus_value, count in sorted(focus_counts.items()):
        target_bucket = registered_focus if _resolves_condition(registry, condition_focus_value) else missing_focus
        target_bucket[condition_focus_value] = {
            "count": count,
            "doc_ids": sorted(focus_doc_ids.get(condition_focus_value, set())),
        }

    return {
        "condition_focus": {
            "registered": registered_focus,
            "missing": missing_focus,
        },
        "gold_conditions": _summarize_gold_conditions(gold_rows, registry),
    }


def _count_manifest_condition_focus(
    manifest_rows: list[dict[str, Any]],
) -> tuple[Counter[str], dict[str, set[str]]]:
    condition_focus_counts: Counter[str] = Counter()
    doc_ids_by_condition_focus: dict[str, set[str]] = {}
    for manifest_row in manifest_rows:
        doc_id = str(manifest_row.get("doc_id") or "")
        for condition_focus_value in manifest_row.get("disease_focus", []) or []:
            normalized_value = str(condition_focus_value).strip()
            if not normalized_value:
                continue
            condition_focus_counts[normalized_value] += 1
            if doc_id:
                doc_ids_by_condition_focus.setdefault(normalized_value, set()).add(doc_id)
    return condition_focus_counts, doc_ids_by_condition_focus


def _summarize_gold_conditions(
    gold_rows: list[dict[str, Any]],
    registry: ConceptRegistry,
) -> dict[str, list[str]]:
    registered: set[str] = set()
    missing: set[str] = set()
    for gold_evaluation_row in gold_rows:
        condition = gold_evaluation_row.get("condition")
        if not isinstance(condition, dict):
            continue
        condition_value = str(condition.get("value") or "").strip()
        if not condition_value:
            continue
        if _resolves_condition(registry, condition_value):
            registered.add(condition_value)
        else:
            missing.add(condition_value)
    return {
        "registered": sorted(registered),
        "missing": sorted(missing),
    }


def _resolves_condition(registry: ConceptRegistry, value: str) -> bool:
    for condition_value in _condition_value_candidates(value):
        try:
            registry.require(CodeKind.CONDITION, condition_value)
            return True
        except ValueError:
            pass
        try:
            registry.resolve_alias(CodeKind.CONDITION, condition_value)
            return True
        except ValueError:
            pass
    return False


def _condition_value_candidates(value: str) -> tuple[str, ...]:
    raw_value = value.strip()
    normalized_value = raw_value.lower().replace("-", "_").replace(" ", "_")
    if normalized_value == raw_value:
        return (raw_value,)
    return (raw_value, normalized_value)
