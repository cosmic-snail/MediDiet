from __future__ import annotations

from knowledge.extraction_comparators import ComparatorInput, FakeExtractorProvider, run_comparator_arm


def test_one_shot_and_two_stage_arms_emit_comparable_observations():
    provider = FakeExtractorProvider(response={"rules": [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}], "evidence_quote": "Adults should reduce sodium intake to less than 2 g/day."}], "suggested_concepts": []})
    comparator_input = ComparatorInput(experiment_id="E2", arm_id="C4", dataset_id="rule_extraction_v1", doc_id="en_guideline_who_sodium_2012", input_variant="extractable_content", text="Adults should reduce sodium intake to less than 2 g/day.", source_card_hash="sha256:source", chunk_hashes=("sha256:chunk",))
    observation = run_comparator_arm(comparator_input, provider=provider)
    assert observation["experiment_id"] == "E2"
    assert observation["arm_id"] == "C4"
    assert observation["observation_points"]["O5"]["input_variant"] == "extractable_content"
    assert observation["observation_points"]["O8"]["parsed_rule_count"] == 1
    assert observation["parsed_rules"][0]["nutrition_limits"][0]["metric"] == "sodium_mg"
