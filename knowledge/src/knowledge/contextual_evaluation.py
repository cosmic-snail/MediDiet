from __future__ import annotations

from typing import Any


def evaluate_contextual_expectation(
    expectation: dict[str, Any], extracted_rules: list[dict[str, Any]]
) -> dict[str, Any]:
    forbidden_metrics = {
        str(metric)
        for overclaim_record in expectation.get("forbidden_overclaims", []) or []
        if overclaim_record.get("type") == "numeric_limit"
        for metric in overclaim_record.get("metrics", []) or []
    }
    overclaim_failures: list[str] = []
    matched_context = False
    expected_context = expectation.get("expected_context", {}) or {}
    expected_condition = str(expected_context.get("condition") or "")
    expected_pattern_tags = {str(tag) for tag in expected_context.get("pattern_tags", []) or []}

    for extracted_rule in extracted_rules:
        for nutrition_limit in extracted_rule.get("nutrition_limits", []) or []:
            metric = str(nutrition_limit.get("metric") or "")
            if metric in forbidden_metrics:
                overclaim_failures.append(f"unexpected_numeric_limit:{metric}")
        condition = _code_value(extracted_rule.get("condition"))
        preferred_tags = {_code_value(tag) for tag in extracted_rule.get("preferred_tags", []) or []}
        if condition == expected_condition or expected_pattern_tags & preferred_tags:
            matched_context = True

    failures: list[str] = []
    if overclaim_failures:
        failures.append("contextual_overclaim")
    if extracted_rules and not matched_context:
        failures.append("context_mismatch")

    return {
        "gold_id": expectation.get("gold_id"),
        "track": "contextual_handling",
        "overall": "match" if not failures else "mismatch",
        "matched_context": matched_context,
        "overclaim_failures": sorted(set(overclaim_failures)),
        "failures": failures,
    }


def _code_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")
