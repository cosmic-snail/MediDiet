from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from medidiet.rules import NutrientMetric


PLAUSIBILITY_ORDER = {"pass": 0, "warn": 1, "fail": 2}

NUMERIC_LIMIT_RANGES: dict[str, tuple[float, float]] = {
    "energy_kcal": (10, 5000),
    "carbs_g": (1, 1000),
    "fat_g": (1, 500),
    "sodium_mg": (100, 6000),
    "sugar_g": (1, 300),
}


@dataclass(frozen=True)
class PlausibilityContext:
    condition_metric_pairs: set[tuple[str, str]]
    known_conditions: set[str]
    known_metrics: set[str]


def build_plausibility_context(manifest_rows: list[dict[str, Any]]) -> PlausibilityContext:
    condition_metric_pairs: set[tuple[str, str]] = set()
    known_conditions: set[str] = set()
    known_metrics = {metric.value for metric in NutrientMetric}
    for manifest_row in manifest_rows:
        disease_focus_values = _string_list(manifest_row.get("disease_focus"))
        nutrition_focus_values = _string_list(manifest_row.get("nutrition_focus"))
        known_conditions.update(disease_focus_values)
        for condition in disease_focus_values:
            for metric in nutrition_focus_values:
                if metric in known_metrics:
                    condition_metric_pairs.add((condition, metric))
    return PlausibilityContext(
        condition_metric_pairs=condition_metric_pairs,
        known_conditions=known_conditions,
        known_metrics=known_metrics,
    )


def evaluate_rule_plausibility(
    rule: dict[str, Any],
    manifest_row: dict[str, Any],
    context: PlausibilityContext,
) -> dict[str, Any]:
    issue_codes: list[str] = []
    condition = _condition_value(rule.get("condition"))
    if not condition:
        issue_codes.append("missing_condition")

    manifest_conditions = set(_string_list(manifest_row.get("disease_focus")))
    if condition and manifest_conditions and condition not in manifest_conditions:
        issue_codes.append("condition_not_in_source_focus")

    for nutrition_limit_index, nutrition_limit in enumerate(rule.get("nutrition_limits", []) or []):
        if not isinstance(nutrition_limit, dict):
            issue_codes.append(f"malformed_nutrition_limit[{nutrition_limit_index}]")
            continue
        metric = str(nutrition_limit.get("metric") or "")
        if metric not in context.known_metrics:
            issue_codes.append("unsupported_metric")
            continue
        if condition and (condition, metric) not in context.condition_metric_pairs:
            issue_codes.append("unusual_condition_metric_pair")
        max_value = nutrition_limit.get("max_value")
        if not _is_numeric_limit_in_range(metric, max_value):
            issue_codes.append("numeric_limit_out_of_range")

    if any(issue.startswith("malformed_") or issue in {"missing_condition", "unsupported_metric"} for issue in issue_codes):
        flag = "fail"
    elif issue_codes:
        flag = "warn"
    else:
        flag = "pass"
    return {
        "plausibility_flag": flag,
        "issue_codes": sorted(set(issue_codes), key=issue_codes.index),
    }


def evaluate_observation_plausibility(
    observation_record: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
    context: PlausibilityContext | None = None,
) -> dict[str, Any]:
    context = context or build_plausibility_context(manifest_rows)
    manifest_by_doc_id = {str(row.get("doc_id")): row for row in manifest_rows}
    manifest_row = manifest_by_doc_id.get(str(observation_record.get("doc_id")), {})
    rule_results = [
        evaluate_rule_plausibility(rule, manifest_row, context)
        for rule in observation_record.get("parsed_rules", []) or []
        if isinstance(rule, dict)
    ]
    plausibility_flag = _worst_flag(result["plausibility_flag"] for result in rule_results)
    return {
        "plausibility_flag": plausibility_flag,
        "rule_count": len(rule_results),
        "rule_results": rule_results,
        "issue_counts": _issue_counts(rule_results),
    }


def _worst_flag(flags: Any) -> str:
    worst = "pass"
    for flag in flags:
        if PLAUSIBILITY_ORDER.get(str(flag), 0) > PLAUSIBILITY_ORDER[worst]:
            worst = str(flag)
    return worst


def _issue_counts(rule_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rule_result in rule_results:
        for issue_code in rule_result.get("issue_codes", []):
            counts[str(issue_code)] = counts.get(str(issue_code), 0) + 1
    return dict(sorted(counts.items()))


def _condition_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _is_numeric_limit_in_range(metric: str, value: Any) -> bool:
    if metric not in NUMERIC_LIMIT_RANGES:
        return True
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    minimum, maximum = NUMERIC_LIMIT_RANGES[metric]
    return minimum <= numeric_value <= maximum
