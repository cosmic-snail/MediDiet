from knowledge.contextual_evaluation import evaluate_contextual_expectation


def test_contextual_evaluation_accepts_pattern_rule_without_numeric_overclaim():
    expectation = {
        "gold_id": "gold-pattern",
        "expected_context": {
            "condition": "cardiovascular_risk",
            "nutrition_signal": "dietary_pattern",
            "pattern_tags": ["mediterranean_pattern", "nuts", "olive_oil"],
        },
        "forbidden_overclaims": [{"type": "numeric_limit", "metrics": ["fat_g", "sodium_mg"]}],
    }
    extracted_rules = [
        {
            "condition": "cardiovascular_risk",
            "preferred_tags": ["mediterranean_pattern", "nuts"],
            "nutrition_limits": [],
        }
    ]

    evaluation = evaluate_contextual_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["overclaim_failures"] == []


def test_contextual_evaluation_rejects_invented_numeric_limit():
    expectation = {
        "gold_id": "gold-pattern",
        "expected_context": {
            "condition": "cardiovascular_risk",
            "nutrition_signal": "dietary_pattern",
            "pattern_tags": ["mediterranean_pattern"],
        },
        "forbidden_overclaims": [{"type": "numeric_limit", "metrics": ["fat_g", "sodium_mg"]}],
    }
    extracted_rules = [
        {
            "condition": "cardiovascular_risk",
            "preferred_tags": ["mediterranean_pattern"],
            "nutrition_limits": [{"metric": "fat_g", "scope": "daily", "max_value": 30}],
        }
    ]

    evaluation = evaluate_contextual_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "mismatch"
    assert evaluation["overclaim_failures"] == ["unexpected_numeric_limit:fat_g"]
