from __future__ import annotations

from typing import Any


def evaluate_conversion_expectation(
    expectation: dict[str, Any],
    extracted_conversion: dict[str, Any] | None,
    *,
    tolerance: float = 0.001,
) -> dict[str, Any]:
    if extracted_conversion is None:
        return {
            "gold_id": expectation.get("gold_id"),
            "track": "conversion",
            "overall": "miss",
            "missing_assumptions": [
                str(required_assumption["name"])
                for required_assumption in expectation.get("required_assumptions", []) or []
            ],
            "value_error": None,
            "failures": ["missing_conversion"],
        }

    required_assumptions = expectation.get("required_assumptions", []) or []
    provided_assumptions = extracted_conversion.get("assumptions", {}) or {}
    missing_assumptions = [
        str(required_assumption["name"])
        for required_assumption in required_assumptions
        if str(required_assumption["name"]) not in provided_assumptions
    ]
    expected_value = float(expectation["target_expression"]["max_value"])
    observed_value = float(extracted_conversion.get("target_value", 0))
    value_error = abs(observed_value - expected_value)
    source_metric_matches = extracted_conversion.get("source_metric") == expectation["source_expression"]["metric"]
    target_metric_matches = extracted_conversion.get("target_metric") == expectation["target_expression"]["metric"]

    failures: list[str] = []
    if missing_assumptions:
        failures.append("missing_conversion_assumption")
    if not source_metric_matches or not target_metric_matches:
        failures.append("conversion_metric_mismatch")
    if value_error > tolerance:
        failures.append("conversion_value_mismatch")

    return {
        "gold_id": expectation.get("gold_id"),
        "track": "conversion",
        "overall": "match" if not failures else "miss",
        "missing_assumptions": missing_assumptions,
        "value_error": value_error,
        "failures": failures,
    }
