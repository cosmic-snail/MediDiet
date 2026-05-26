from __future__ import annotations

from knowledge.rule_evaluation import evaluate_rule


def test_evaluate_numeric_rule_match():
    gold = {"gold_id": "gold-sodium", "should_extract": True, "condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}]}
    extracted = [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}], "evidence_quote": "less than 2 g/day"}]
    result = evaluate_rule(gold, extracted)
    assert result["field_scores"]["nutrition_limits"] == "match"
    assert result["overall"] == "match"


def test_no_rule_expected_example():
    result = evaluate_rule({"gold_id": "none", "should_extract": False}, [])
    assert result["overall"] == "match"


def test_concept_gap_alias_is_reporting_only():
    gold = {"gold_id": "gap", "should_extract": True, "condition": "ckd", "suggested_concepts": ["potassium_phosphorus_management"], "nutrition_limits": []}
    extracted = [{"condition": "ckd", "suggested_concepts": ["potassium_management", "phosphorus_management"], "nutrition_limits": []}]
    assert "suggested_concept_mismatch" not in evaluate_rule(gold, extracted)["failures"]


def test_challenge_example_excluded_from_ordinary_f1():
    result = evaluate_rule({"gold_id": "challenge", "split": "challenge", "should_extract": True}, [])
    assert result["excluded_from_f1"] is True
