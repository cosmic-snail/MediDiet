from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any


def _limit_key(limit: dict[str, Any]) -> str:
    return "|".join(str(limit.get(k)) for k in ("metric", "scope", "max_value", "window_hours"))


def _rule_keys(observation_record: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for rule in observation_record.get("parsed_rules", []):
        keys.add(f"condition:{rule.get('condition')}")
        for tag in rule.get("preferred_tags", []) or []:
            keys.add(f"tag:{tag}")
        for exclusion in rule.get("hard_exclusions", []) or []:
            keys.add(f"exclusion:{exclusion}")
        for limit in rule.get("nutrition_limits", []) or []:
            keys.add(f"limit:{_limit_key(limit)}")
    return keys


def _presence(counter: Counter[str], total: int) -> dict[str, float]:
    if total == 0:
        return {}
    return {key: count / total for key, count in sorted(counter.items())}


def summarize_stability(observation_records: list[dict]) -> dict:
    run_count = len(observation_records)
    conditions: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    limits: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    retry_counts: Counter[int] = Counter()
    empty_outputs = 0
    parse_failures = 0
    for observation_record in observation_records:
        failures.update(observation_record.get("failures", []))
        retry_counts[observation_record.get("retry_count", 0)] += 1
        if not observation_record.get("parsed_rules"):
            empty_outputs += 1
        if observation_record.get("parse_status") not in (None, "parsed"):
            parse_failures += 1
        seen_conditions: set[str] = set()
        seen_exclusions: set[str] = set()
        seen_tags: set[str] = set()
        seen_limits: set[str] = set()
        for rule in observation_record.get("parsed_rules", []):
            if rule.get("condition"):
                seen_conditions.add(str(rule["condition"]))
            seen_exclusions.update(map(str, rule.get("hard_exclusions", []) or []))
            seen_tags.update(map(str, rule.get("preferred_tags", []) or []))
            for limit in rule.get("nutrition_limits", []) or []:
                seen_limits.add(_limit_key(limit))
        conditions.update(seen_conditions)
        exclusions.update(seen_exclusions)
        tags.update(seen_tags)
        limits.update(seen_limits)

    similarities: list[float] = []
    for left, right in combinations(observation_records, 2):
        left_keys = _rule_keys(left)
        right_keys = _rule_keys(right)
        union = left_keys | right_keys
        similarities.append(len(left_keys & right_keys) / len(union) if union else 1.0)
    return {
        "run_count": run_count,
        "condition_presence": _presence(conditions, run_count),
        "hard_exclusion_presence": _presence(exclusions, run_count),
        "preferred_tag_presence": _presence(tags, run_count),
        "nutrition_limit_presence": _presence(limits, run_count),
        "parse_failure_rate": parse_failures / run_count if run_count else 0.0,
        "empty_output_rate": empty_outputs / run_count if run_count else 0.0,
        "retry_count_distribution": {str(k): v for k, v in sorted(retry_counts.items())},
        "pairwise_canonical_rule_set_similarity": sum(similarities) / len(similarities) if similarities else 1.0,
        "failure_counts": dict(failures),
    }
