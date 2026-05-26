from __future__ import annotations

from knowledge.rule_identity import canonical_rule_identity, diff_rule_sets


def test_canonical_rule_identity_ignores_ordering_noise():
    first = {"condition": "hypertension", "hard_exclusions": ["kidney_failure", "heart_failure"], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}]}
    second = {"condition": "hypertension", "hard_exclusions": ["heart_failure", "kidney_failure"], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"scope": "daily", "metric": "sodium_mg", "window_hours": 24, "max_value": 2000}]}
    assert canonical_rule_identity(first) == canonical_rule_identity(second)


def test_diff_rule_sets_reports_added_removed_and_conflicts():
    previous = [{"condition": "hypertension", "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}]}]
    current = [{"condition": "hypertension", "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 1500, "window_hours": 24}]}]
    diff = diff_rule_sets(previous, current)
    assert diff["added"]
    assert diff["removed"]
    assert diff["conflicts"]
