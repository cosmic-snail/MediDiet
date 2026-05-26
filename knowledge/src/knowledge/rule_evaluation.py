from __future__ import annotations

from typing import Any


SUGGESTED_CONCEPT_ALIASES = {
    "potassium_phosphorus_management": {"potassium_management", "phosphorus_management"},
}


def _limits(rule: dict[str, Any]) -> set[tuple]:
    return {
        (item.get("metric"), item.get("scope"), float(item.get("max_value", 0)), item.get("window_hours"))
        for item in rule.get("nutrition_limits", []) or []
    }


def _soft_concepts(values: list[str]) -> set[str]:
    result = set(values)
    for value in values:
        aliases = SUGGESTED_CONCEPT_ALIASES.get(value, set())
        if aliases:
            result.discard(value)
            result.update(aliases)
    return result


def evaluate_rule(gold: dict[str, Any], extracted: list[dict[str, Any]], include_challenge: bool = False) -> dict[str, Any]:
    if gold.get("split") == "challenge" and not include_challenge:
        return {"gold_id": gold.get("gold_id"), "excluded_from_f1": True, "overall": "challenge_only", "field_scores": {}, "failures": []}
    if gold.get("should_extract") is False:
        failures = [] if not extracted else ["unexpected_numeric_limit"]
        return {"gold_id": gold.get("gold_id"), "field_scores": {"no_rule_expected": "match" if not extracted else "extra"}, "overall": "match" if not extracted else "mismatch", "failures": failures}
    best = extracted[0] if extracted else {}
    fields: dict[str, str] = {}
    failures: list[str] = []
    fields["condition"] = "match" if best.get("condition") == gold.get("condition") else "missing"
    if fields["condition"] != "match":
        failures.append("condition_mismatch")
    fields["hard_exclusions"] = "match" if set(best.get("hard_exclusions", []) or []) == set(gold.get("hard_exclusions", []) or []) else "partial"
    fields["preferred_tags"] = "match" if set(best.get("preferred_tags", []) or []) == set(gold.get("preferred_tags", []) or []) else "partial"
    gold_limits = _limits(gold)
    extracted_limits = _limits(best)
    if gold_limits <= extracted_limits:
        fields["nutrition_limits"] = "match"
    elif gold_limits and not extracted_limits:
        fields["nutrition_limits"] = "missing"
        failures.append("missing_numeric_limit")
    else:
        fields["nutrition_limits"] = "partial"
    quote = best.get("evidence_quote", "") or best.get("evidence_quotes", "")
    fields["evidence_quote"] = "partial" if quote else "missing"
    concepts = _soft_concepts(best.get("suggested_concepts", []) or [])
    expected_concepts = _soft_concepts(gold.get("suggested_concepts", []) or [])
    if expected_concepts and not expected_concepts <= concepts:
        failures.append("suggested_concept_mismatch")
    if not extracted:
        failures.append("no_rule_extracted")
    overall = "match" if all(value == "match" for key, value in fields.items() if key != "evidence_quote") else "partial_match"
    if "missing" in fields.values() and fields.get("nutrition_limits") == "missing":
        overall = "miss"
    return {"gold_id": gold.get("gold_id"), "field_scores": fields, "overall": overall, "failures": failures}


def precision_recall_f1(evaluations: list[dict[str, Any]]) -> dict[str, float]:
    scored = [item for item in evaluations if not item.get("excluded_from_f1")]
    tp = sum(1 for item in scored if item.get("overall") in {"match", "partial_match"})
    fn = sum(1 for item in scored if item.get("overall") == "miss")
    fp = sum(1 for item in scored if "unexpected_numeric_limit" in item.get("failures", []))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
