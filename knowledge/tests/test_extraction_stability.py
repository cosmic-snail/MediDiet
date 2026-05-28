from __future__ import annotations

from knowledge.extraction_stability import summarize_stability


def test_summarize_stability_detects_field_variance():
    runs = [{"parsed_rules": [{"condition": "diabetes", "preferred_tags": ["low_sugar"], "nutrition_limits": [{"metric": "sugar_g", "scope": "daily", "max_value": 25, "window_hours": 24}]}], "failures": []}, {"parsed_rules": [{"condition": "diabetes", "preferred_tags": ["low_sugar"], "nutrition_limits": []}], "failures": ["missing_numeric_limit"]}]
    summary = summarize_stability(runs)
    assert summary["run_count"] == 2
    assert summary["condition_presence"]["diabetes"] == 1.0
    assert summary["nutrition_limit_presence"]["sugar_g|daily|25|24"] == 0.5
    assert "missing_numeric_limit" in summary["failure_counts"]
