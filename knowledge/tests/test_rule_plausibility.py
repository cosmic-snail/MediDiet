from __future__ import annotations

from knowledge.rule_plausibility import (
    build_plausibility_context,
    evaluate_observation_plausibility,
    evaluate_rule_plausibility,
)


def test_plausibility_warns_for_unusual_condition_metric_pair_without_failing():
    manifest_rows = [
        {
            "doc_id": "doc-hypertension",
            "disease_focus": ["hypertension"],
            "nutrition_focus": ["sodium_mg"],
        }
    ]
    context = build_plausibility_context(manifest_rows)
    rule = {
        "condition": "hypertension",
        "nutrition_limits": [
            {"metric": "sugar_g", "scope": "daily", "max_value": 25, "window_hours": 24}
        ],
    }

    result = evaluate_rule_plausibility(rule, manifest_rows[0], context)

    assert result["plausibility_flag"] == "warn"
    assert "unusual_condition_metric_pair" in result["issue_codes"]


def test_plausibility_fails_only_for_hard_schema_problems():
    context = build_plausibility_context([])
    result = evaluate_rule_plausibility({"nutrition_limits": []}, {}, context)

    assert result["plausibility_flag"] == "fail"
    assert "missing_condition" in result["issue_codes"]


def test_observation_plausibility_summarizes_worst_rule_flag():
    manifest_rows = [
        {
            "doc_id": "doc-hypertension",
            "disease_focus": ["hypertension"],
            "nutrition_focus": ["sodium_mg"],
        }
    ]
    context = build_plausibility_context(manifest_rows)
    observation = {
        "doc_id": "doc-hypertension",
        "parsed_rules": [
            {
                "condition": "hypertension",
                "nutrition_limits": [
                    {"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}
                ],
            },
            {
                "condition": "hypertension",
                "nutrition_limits": [
                    {"metric": "sodium_mg", "scope": "daily", "max_value": 10000, "window_hours": 24}
                ],
            },
        ],
    }

    result = evaluate_observation_plausibility(observation, manifest_rows, context)

    assert result["plausibility_flag"] == "warn"
    assert result["rule_count"] == 2
    assert result["rule_results"][1]["issue_codes"] == ["numeric_limit_out_of_range"]
