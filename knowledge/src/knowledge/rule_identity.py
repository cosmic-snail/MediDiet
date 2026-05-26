from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_limit(limit: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric": str(limit.get("metric", "")).lower(),
        "scope": str(limit.get("scope", "")).lower(),
        "max_value": float(limit.get("max_value", 0)),
        "window_hours": limit.get("window_hours"),
    }


def canonical_rule_payload(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "condition": str(rule.get("condition", "")).lower(),
        "hard_exclusions": sorted(map(str, rule.get("hard_exclusions", []) or [])),
        "preferred_tags": sorted(map(str, rule.get("preferred_tags", []) or [])),
        "nutrition_limits": sorted((_canonical_limit(limit) for limit in rule.get("nutrition_limits", []) or []), key=lambda item: json.dumps(item, sort_keys=True)),
        "source_class": str(rule.get("source_class", rule.get("authority_class", ""))).lower(),
        "provenance_level": str(rule.get("provenance_level", "")).lower(),
    }


def canonical_rule_identity(rule: dict[str, Any]) -> str:
    encoded = json.dumps(canonical_rule_payload(rule), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _identity_map(rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {canonical_rule_identity(rule): rule for rule in rules}


def _has_numeric_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_limits = left.get("nutrition_limits", []) or []
    right_limits = right.get("nutrition_limits", []) or []
    for left_limit in left_limits:
        for right_limit in right_limits:
            if left_limit.get("metric") == right_limit.get("metric") and left_limit.get("scope") == right_limit.get("scope") and left_limit.get("max_value") != right_limit.get("max_value"):
                return True
    return False


def diff_rule_sets(previous: list[dict], current: list[dict]) -> dict:
    previous_map = _identity_map(previous)
    current_map = _identity_map(current)
    previous_ids = set(previous_map)
    current_ids = set(current_map)
    near_duplicates: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    for prev_id, prev_rule in previous_map.items():
        for curr_id, curr_rule in current_map.items():
            if prev_id == curr_id:
                continue
            if prev_rule.get("condition") == curr_rule.get("condition"):
                if set(prev_rule.get("preferred_tags", []) or []) & set(curr_rule.get("preferred_tags", []) or []):
                    near_duplicates.append({"previous": prev_id, "current": curr_id})
                if _has_numeric_conflict(prev_rule, curr_rule):
                    conflicts.append({"previous": prev_id, "current": curr_id, "type": "numeric_threshold_conflict"})
    return {
        "added": sorted(current_ids - previous_ids),
        "removed": sorted(previous_ids - current_ids),
        "changed": [],
        "unchanged": sorted(previous_ids & current_ids),
        "near_duplicates": near_duplicates,
        "conflicts": conflicts,
    }
