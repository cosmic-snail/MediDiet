from __future__ import annotations

from knowledge.rule_evaluation import evaluate_rule


def test_evaluate_numeric_rule_match():
    gold = {"gold_id": "gold-sodium", "should_extract": True, "condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}]}
    extracted = [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}], "evidence_quote": "less than 2 g/day"}]
    result = evaluate_rule(gold, extracted)
    assert result["field_scores"]["nutrition_limits"] == "match"
    assert result["overall"] == "match"


def test_numeric_limit_metric_mismatch_is_reported_separately():
    gold = {"gold_id": "gold-sodium", "should_extract": True, "condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}]}
    extracted = [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sugar_g", "scope": "daily", "max_value": 50, "window_hours": 24}], "evidence_quote": "less than 2 g/day"}]

    result = evaluate_rule(gold, extracted)

    assert result["field_scores"]["nutrition_limits"] == "partial"
    assert "numeric_limit_metric_mismatch" in result["failures"]
    assert "missing_numeric_limit" not in result["failures"]


def test_numeric_limit_value_mismatch_is_reported_separately():
    gold = {"gold_id": "gold-sodium", "should_extract": True, "condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}]}
    extracted = [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 1500, "window_hours": 24}], "evidence_quote": "less than 1.5 g/day"}]

    result = evaluate_rule(gold, extracted)

    assert result["field_scores"]["nutrition_limits"] == "partial"
    assert "numeric_limit_value_mismatch" in result["failures"]
    assert "missing_numeric_limit" not in result["failures"]


def test_daily_numeric_limit_matches_null_or_24_hour_window():
    gold = {"gold_id": "gold-sodium", "should_extract": True, "condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": None}]}
    extracted = [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}], "evidence_quote": "2000 mg sodium per day"}]

    result = evaluate_rule(gold, extracted)

    assert result["field_scores"]["nutrition_limits"] == "match"
    assert "numeric_limit_value_mismatch" not in result["failures"]


def test_no_rule_expected_example():
    result = evaluate_rule({"gold_id": "none", "should_extract": False}, [])
    assert result["overall"] == "match"


def test_negative_rule_failure_labels_distinguish_contextual_and_numeric_outputs():
    gold = {"gold_id": "negative", "gold_behavior": "negative", "should_extract": False}

    numeric_evaluation = evaluate_rule(gold, [{"nutrition_limits": [{"metric": "sodium_mg"}]}])
    contextual_evaluation = evaluate_rule(gold, [{"preferred_tags": ["mediterranean_pattern"], "nutrition_limits": []}])
    concept_evaluation = evaluate_rule(gold, [{"suggested_concepts": ["low_purine"]}])

    assert numeric_evaluation["failures"] == ["unexpected_numeric_limit"]
    assert contextual_evaluation["failures"] == ["unexpected_contextual_rule"]
    assert concept_evaluation["failures"] == ["unexpected_suggested_concept"]


def test_umbrella_concept_is_not_soft_matched_in_clean_rule_evaluation():
    gold = {
        "gold_id": "gap",
        "gold_behavior": "suggested_concept",
        "suggested_concepts": ["potassium_phosphorus_management"],
    }
    extracted = [{"suggested_concepts": ["potassium_management", "phosphorus_management"]}]

    evaluation = evaluate_rule(gold, extracted)

    assert evaluation["overall"] == "miss"
    assert "suggested_concept_mismatch" in evaluation["failures"]


def test_challenge_example_excluded_from_ordinary_f1():
    result = evaluate_rule({"gold_id": "challenge", "split": "challenge", "should_extract": True}, [])
    assert result["excluded_from_f1"] is True
