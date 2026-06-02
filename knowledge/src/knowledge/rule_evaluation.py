from __future__ import annotations

from typing import Any


# Umbrella-to-atomic concept matching belongs to the concept discovery track.
# Mixed rule evaluation keeps suggested concepts literal for backward-compatible reporting.


def _limits(rule: dict[str, Any]) -> set[tuple]:
    return {
        (
            item.get("metric"),
            item.get("scope"),
            float(item.get("max_value", 0)),
            _normalized_limit_window(item.get("scope"), item.get("window_hours")),
        )
        for item in rule.get("nutrition_limits", []) or []
    }


def _normalized_limit_window(scope: Any, window_hours: Any) -> Any:
    if scope == "daily" and window_hours in {None, 24, "24"}:
        return 24
    return window_hours


def _numeric_limit_failure_labels(gold_limits: set[tuple], extracted_limits: set[tuple]) -> list[str]:
    if not gold_limits:
        return []
    if not extracted_limits:
        return ["missing_numeric_limit"]

    gold_metrics = {item[0] for item in gold_limits}
    extracted_metrics = {item[0] for item in extracted_limits}
    if not gold_metrics & extracted_metrics:
        return ["numeric_limit_metric_mismatch"]

    gold_metric_scopes = {(item[0], item[1]) for item in gold_limits}
    extracted_metric_scopes = {(item[0], item[1]) for item in extracted_limits}
    if not gold_metric_scopes & extracted_metric_scopes:
        return ["numeric_limit_scope_mismatch"]

    return ["numeric_limit_value_mismatch"]


def _code_value(item: Any) -> Any:
    if isinstance(item, dict):
        return item.get("value")
    return item


def _code_values(items: list[Any] | None) -> set[str]:
    return {str(value) for value in (_code_value(item) for item in items or []) if value}


def _unexpected_negative_failures(extracted: list[dict[str, Any]]) -> list[str]:
    failures: set[str] = set()
    for extracted_rule in extracted:
        if extracted_rule.get("nutrition_limits"):
            failures.add("unexpected_numeric_limit")
        if extracted_rule.get("suggested_concepts"):
            failures.add("unexpected_suggested_concept")
        if extracted_rule.get("preferred_tags") and not extracted_rule.get("nutrition_limits"):
            failures.add("unexpected_contextual_rule")
    return sorted(failures) or ["unexpected_rule"]


def evaluate_rule(gold: dict[str, Any], extracted: list[dict[str, Any]], include_challenge: bool = False) -> dict[str, Any]:
    if gold.get("split") == "challenge" and not include_challenge:
        return {"gold_id": gold.get("gold_id"), "excluded_from_f1": True, "overall": "challenge_only", "field_scores": {}, "failures": []}
    if gold.get("should_extract") is False or gold.get("gold_behavior") == "negative":
        failures = [] if not extracted else _unexpected_negative_failures(extracted)
        return {"gold_id": gold.get("gold_id"), "field_scores": {"no_rule_expected": "match" if not extracted else "extra"}, "overall": "match" if not extracted else "mismatch", "failures": failures}
    if gold.get("gold_behavior") == "suggested_concept":
        suggestions = {
            str(item.get("suggested_code", item) if isinstance(item, dict) else item)
            for rule in extracted
            for item in rule.get("suggested_concepts", []) or []
        }
        expected = {str(item) for item in gold.get("suggested_concepts", []) or []}
        failures = [] if expected <= suggestions else ["suggested_concept_mismatch"]
        return {
            "gold_id": gold.get("gold_id"),
            "field_scores": {"suggested_concepts": "match" if not failures else "missing"},
            "overall": "match" if not failures else "miss",
            "failures": failures,
        }
    best = extracted[0] if extracted else {}
    fields: dict[str, str] = {}
    failures: list[str] = []
    fields["condition"] = "match" if _code_value(best.get("condition")) == _code_value(gold.get("condition")) else "missing"
    if fields["condition"] != "match":
        failures.append("condition_mismatch")
    fields["hard_exclusions"] = "match" if _code_values(best.get("hard_exclusions")) == _code_values(gold.get("hard_exclusions")) else "partial"
    fields["preferred_tags"] = "match" if _code_values(best.get("preferred_tags")) == _code_values(gold.get("preferred_tags")) else "partial"
    gold_limits = _limits(gold)
    extracted_limits = _limits(best)
    if gold_limits <= extracted_limits:
        fields["nutrition_limits"] = "match"
    elif gold_limits and not extracted_limits:
        fields["nutrition_limits"] = "missing"
        failures.append("missing_numeric_limit")
    else:
        fields["nutrition_limits"] = "partial"
        failures.extend(_numeric_limit_failure_labels(gold_limits, extracted_limits))
    quote = best.get("evidence_quote", "") or best.get("evidence_quotes", "")
    fields["evidence_quote"] = "partial" if quote else "missing"
    concepts = {str(item) for item in best.get("suggested_concepts", []) or []}
    expected_concepts = {str(item) for item in gold.get("suggested_concepts", []) or []}
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
