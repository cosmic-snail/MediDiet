from __future__ import annotations

from knowledge.semantic_grounding import evaluate_observation_grounding, evaluate_rule_grounding


def test_grounding_scores_rule_when_condition_and_numeric_limit_are_supported():
    source_text = "For hypertension, adults should reduce sodium intake to less than 2 g/day."
    rule = {
        "condition": "hypertension",
        "preferred_tags": ["low_sodium"],
        "hard_exclusions": ["high_sodium"],
        "nutrition_limits": [
            {"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}
        ],
        "evidence_quote": "less than 2 g/day",
    }

    result = evaluate_rule_grounding(rule, source_text)

    assert result["grounding_score"] == 1.0
    assert result["unsupported_fields"] == []


def test_grounding_marks_unsupported_numeric_limit():
    source_text = "For hypertension, adults should reduce sodium intake."
    rule = {
        "condition": "hypertension",
        "nutrition_limits": [
            {"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}
        ],
    }

    result = evaluate_rule_grounding(rule, source_text)

    assert result["grounding_score"] < 1.0
    assert "nutrition_limits[0]" in result["unsupported_fields"]


def test_observation_grounding_summarizes_average_score():
    observation = {
        "parsed_rules": [
            {"condition": "hypertension", "nutrition_limits": [{"metric": "sodium_mg", "max_value": 2000}]},
            {"condition": "diabetes", "nutrition_limits": [{"metric": "sugar_g", "max_value": 25}]},
        ]
    }
    source_text = "Hypertension sodium guidance says less than 2000 mg. Diabetes guidance limits sugar to 25 g."

    result = evaluate_observation_grounding(observation, source_text)

    assert result["rule_count"] == 2
    assert result["avg_score"] == 1.0
    assert result["unsupported_rate"] == 0.0
