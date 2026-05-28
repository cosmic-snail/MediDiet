from __future__ import annotations

from collections import defaultdict
from typing import Any


SOURCE_TYPE_GOVERNANCE = {
    "guideline": {"authority_class": "guideline", "authority_rank": 90},
    "paper": {"authority_class": "paper", "authority_rank": 60},
    "food_db": {"authority_class": "reference", "authority_rank": 40},
    "manual": {"authority_class": "synthetic_or_edge_case", "authority_rank": 20},
}


def governance_metadata_for_source_type(source_type: str) -> dict[str, Any]:
    base = SOURCE_TYPE_GOVERNANCE.get(source_type, SOURCE_TYPE_GOVERNANCE["manual"])
    return {
        **base,
        "jurisdiction": "global",
        "audience": "professional",
        "provenance_level": "summary_with_short_excerpt",
        "copyright_mode": "summary_only",
    }


def conflict_key(candidate: dict[str, Any]) -> tuple:
    first_limit = (candidate.get("nutrition_limits") or [{}])[0]
    return (
        candidate.get("condition"),
        first_limit.get("metric"),
        first_limit.get("scope"),
        candidate.get("patient_subgroup", ""),
    )


def detect_conflicts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[conflict_key(candidate)].append(candidate)
    conflicts: list[dict[str, Any]] = []
    for key, items in groups.items():
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                left_limit = (left.get("nutrition_limits") or [{}])[0]
                right_limit = (right.get("nutrition_limits") or [{}])[0]
                if left_limit.get("max_value") != right_limit.get("max_value"):
                    lower, higher = sorted((left, right), key=lambda item: (item.get("nutrition_limits") or [{}])[0].get("max_value", 0))
                    conflict_type = "stricter_numeric_threshold_conflict"
                    if lower.get("authority_rank", 0) < higher.get("authority_rank", 0) and lower.get("year", 0) < higher.get("year", 0):
                        conflict_type = "old_low_authority_cannot_supersede_newer_high_authority"
                    conflicts.append({"group_key": "|".join(map(str, key)), "left": left.get("rule_identity", ""), "right": right.get("rule_identity", ""), "type": conflict_type})
                if left.get("recommendation_direction") and right.get("recommendation_direction") and left.get("recommendation_direction") != right.get("recommendation_direction"):
                    conflicts.append({"group_key": "|".join(map(str, key)), "left": left.get("rule_identity", ""), "right": right.get("rule_identity", ""), "type": "opposite_recommendation_direction"})
    return conflicts
