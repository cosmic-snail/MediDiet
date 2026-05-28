from __future__ import annotations

from knowledge.rule_identity import canonical_rule_identity
from knowledge.source_governance import detect_conflicts, governance_metadata_for_source_type


def test_guideline_metadata_rank_is_higher_than_manual():
    assert governance_metadata_for_source_type("guideline")["authority_rank"] == 90
    assert governance_metadata_for_source_type("manual")["authority_rank"] == 20


def test_old_low_authority_threshold_cannot_silently_supersede_new_guideline():
    guideline = {"condition": "hypertension", "year": 2024, "authority_rank": 90, "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000}], "preferred_tags": ["low_sodium"]}
    blog = {"condition": "hypertension", "year": 2010, "authority_rank": 40, "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 1500}], "preferred_tags": ["low_sodium"]}
    guideline["rule_identity"] = canonical_rule_identity(guideline)
    blog["rule_identity"] = canonical_rule_identity(blog)
    conflicts = detect_conflicts([guideline, blog])
    assert conflicts
    assert conflicts[0]["type"] == "old_low_authority_cannot_supersede_newer_high_authority"
