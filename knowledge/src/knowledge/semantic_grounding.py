from __future__ import annotations

import re
from typing import Any


METRIC_TERMS: dict[str, tuple[str, ...]] = {
    "energy_kcal": ("energy", "calorie", "kcal"),
    "carbs_g": ("carbohydrate", "carb"),
    "fat_g": ("fat",),
    "sodium_mg": ("sodium", "salt"),
    "sugar_g": ("sugar", "sugars"),
}


def evaluate_rule_grounding(rule: dict[str, Any], source_text: str) -> dict[str, Any]:
    evidence_text = _combined_text(source_text, rule)
    field_results: dict[str, bool] = {}

    condition = _condition_value(rule.get("condition"))
    if condition:
        field_results["condition"] = _terms_supported(condition, evidence_text)

    for field_name in ("preferred_tags", "hard_exclusions"):
        values = _code_values(rule.get(field_name))
        if values:
            field_results[field_name] = any(_terms_supported(value, evidence_text) for value in values)

    for nutrition_limit_index, nutrition_limit in enumerate(rule.get("nutrition_limits", []) or []):
        field_key = f"nutrition_limits[{nutrition_limit_index}]"
        if not isinstance(nutrition_limit, dict):
            field_results[field_key] = False
            continue
        metric = str(nutrition_limit.get("metric") or "")
        max_value = nutrition_limit.get("max_value")
        field_results[field_key] = _metric_supported(metric, evidence_text) and _number_supported(metric, max_value, evidence_text)

    supported_count = sum(1 for supported in field_results.values() if supported)
    grounding_score = supported_count / len(field_results) if field_results else 1.0
    unsupported_fields = [field for field, supported in field_results.items() if not supported]
    return {
        "grounding_score": round(grounding_score, 4),
        "unsupported_fields": unsupported_fields,
        "field_results": field_results,
    }


def evaluate_observation_grounding(
    observation_record: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    rule_results = [
        evaluate_rule_grounding(rule, source_text)
        for rule in observation_record.get("parsed_rules", []) or []
        if isinstance(rule, dict)
    ]
    unsupported_rule_count = sum(1 for result in rule_results if result["unsupported_fields"])
    avg_score = sum(result["grounding_score"] for result in rule_results) / len(rule_results) if rule_results else 1.0
    return {
        "rule_count": len(rule_results),
        "avg_score": round(avg_score, 4),
        "unsupported_rate": unsupported_rule_count / len(rule_results) if rule_results else 0.0,
        "rule_results": rule_results,
    }


def _combined_text(source_text: str, rule: dict[str, Any]) -> str:
    evidence_parts: list[str] = [source_text]
    for key in ("evidence_quote", "evidence_quotes"):
        value = rule.get(key)
        if isinstance(value, dict):
            evidence_parts.extend(str(item) for item in value.values())
        elif value:
            evidence_parts.append(str(value))
    return "\n".join(evidence_parts).lower()


def _condition_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")


def _code_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            code_value = item.get("value")
        else:
            code_value = item
        if code_value:
            result.append(str(code_value))
    return result


def _terms_supported(value: str, evidence_text: str) -> bool:
    tokens = [token for token in re.split(r"[_:\W]+", value.lower()) if token]
    return any(token in evidence_text for token in tokens)


def _metric_supported(metric: str, evidence_text: str) -> bool:
    terms = METRIC_TERMS.get(metric, (metric.replace("_", " "),))
    return any(term in evidence_text for term in terms)


def _number_supported(metric: str, value: Any, evidence_text: str) -> bool:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    candidates = _numeric_candidates(metric, numeric_value)
    return any(candidate in evidence_text for candidate in candidates)


def _numeric_candidates(metric: str, numeric_value: float) -> set[str]:
    candidates = {_format_number(numeric_value)}
    if metric.endswith("_mg"):
        candidates.add(_format_number(numeric_value / 1000))
    if metric.endswith("_g"):
        candidates.add(_format_number(numeric_value))
    return candidates


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value).rstrip("0").rstrip(".")
