from __future__ import annotations

from typing import Any


def evaluate_concept_expectation(
    expectation: dict[str, Any], extracted_rules: list[dict[str, Any]]
) -> dict[str, Any]:
    expected_records = expectation.get("expected_atomic_concepts", []) or []
    expected_concept_keys: set[tuple[str, str]] = set()
    canonical_by_surface_form = _build_canonical_surface_map(expectation)
    umbrella_mappings = _build_umbrella_mappings(expectation)
    forbidden_values = {_normalize_surface_value(value) for value in expectation.get("do_not_score_as", []) or []}

    for expected_record in expected_records:
        kind = str(expected_record["kind"])
        value = str(expected_record["value"])
        expected_concept_keys.add((kind, value))

    extracted_concept_keys: set[tuple[str, str]] = set()
    forbidden_matches: set[str] = set()
    linked_surface_forms: set[tuple[str, str]] = set()
    unlinked_surface_forms: set[tuple[str, str]] = set()
    umbrella_covered_keys: set[tuple[str, str]] = set()
    for extracted_rule in extracted_rules:
        for concept_record in extracted_rule.get("suggested_concepts", []) or []:
            if isinstance(concept_record, dict):
                kind = str(concept_record.get("kind") or concept_record.get("suggested_kind") or "nutrition_tag")
                raw_value = str(concept_record.get("suggested_code") or concept_record.get("value") or "")
            else:
                kind = "nutrition_tag"
                raw_value = str(concept_record)
            normalized_value = _normalize_surface_value(raw_value)
            if normalized_value in forbidden_values:
                forbidden_matches.add(normalized_value)
                umbrella_covered_keys.update(umbrella_mappings.get(normalized_value, set()))
                continue
            matched_key = canonical_by_surface_form.get((kind, normalized_value))
            if matched_key is not None:
                extracted_concept_keys.add(matched_key)
                linked_surface_forms.add((kind, normalized_value))
            elif raw_value:
                extracted_concept_keys.add((kind, normalized_value))
                unlinked_surface_forms.add((kind, normalized_value))

    true_positive_keys = expected_concept_keys & extracted_concept_keys
    false_negative_keys = expected_concept_keys - extracted_concept_keys
    false_positive_keys = extracted_concept_keys - expected_concept_keys
    umbrella_coverage = (
        len(expected_concept_keys & umbrella_covered_keys) / len(expected_concept_keys)
        if expected_concept_keys
        else 0.0
    )

    return {
        "gold_id": expectation.get("gold_id"),
        "track": "concept_discovery",
        "overall": "match" if not false_negative_keys else "miss",
        "matched_concepts": _sorted_concepts(true_positive_keys),
        "missing_concepts": _sorted_concepts(false_negative_keys),
        "extra_concepts": _sorted_concepts(false_positive_keys),
        "forbidden_umbrella_matches": sorted(forbidden_matches),
        "atomic_recall": {
            "expected_count": len(expected_concept_keys),
            "matched_count": len(true_positive_keys),
            "missing_count": len(false_negative_keys),
            "recall": len(true_positive_keys) / len(expected_concept_keys) if expected_concept_keys else 0.0,
        },
        "semantic_linking": {
            "linked_count": len(linked_surface_forms),
            "unlinked_values": _sorted_concepts(unlinked_surface_forms),
        },
        "umbrella_decomposition": {
            "coverage": umbrella_coverage,
            "covered_atomic_concepts": _sorted_concepts(expected_concept_keys & umbrella_covered_keys),
            "missing_atomic_concepts": (
                _sorted_concepts(expected_concept_keys - umbrella_covered_keys) if forbidden_matches else []
            ),
        },
        "true_positive_count": len(true_positive_keys),
        "false_negative_count": len(false_negative_keys),
        "false_positive_count": len(false_positive_keys),
    }


def precision_recall_f1_for_concepts(evaluations: list[dict[str, Any]]) -> dict[str, float]:
    true_positive_count = sum(int(evaluation.get("true_positive_count", 0)) for evaluation in evaluations)
    false_negative_count = sum(int(evaluation.get("false_negative_count", 0)) for evaluation in evaluations)
    false_positive_count = sum(int(evaluation.get("false_positive_count", 0)) for evaluation in evaluations)
    precision = (
        true_positive_count / (true_positive_count + false_positive_count)
        if true_positive_count + false_positive_count
        else 0.0
    )
    recall = (
        true_positive_count / (true_positive_count + false_negative_count)
        if true_positive_count + false_negative_count
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def summarize_concept_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    linked_count = sum(
        int((evaluation.get("semantic_linking") or {}).get("linked_count", 0)) for evaluation in evaluations
    )
    unlinked_count = sum(
        len((evaluation.get("semantic_linking") or {}).get("unlinked_values", []) or [])
        for evaluation in evaluations
    )
    umbrella_coverages = [
        float((evaluation.get("umbrella_decomposition") or {}).get("coverage", 0.0))
        for evaluation in evaluations
    ]
    average_umbrella_coverage = sum(umbrella_coverages) / len(umbrella_coverages) if umbrella_coverages else 0.0
    return {
        "atomic": precision_recall_f1_for_concepts(evaluations),
        "semantic_linking": {
            "linked_count": linked_count,
            "unlinked_count": unlinked_count,
        },
        "umbrella_decomposition": {
            "average_coverage": average_umbrella_coverage,
        },
    }


def _sorted_concepts(keys: set[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"kind": kind, "value": value} for kind, value in sorted(keys)]


def _build_canonical_surface_map(expectation: dict[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
    canonical_by_surface_form: dict[tuple[str, str], tuple[str, str]] = {}
    for expected_record in expectation.get("expected_atomic_concepts", []) or []:
        kind = str(expected_record["kind"])
        value = str(expected_record["value"])
        canonical_key = (kind, value)
        canonical_by_surface_form[(kind, _normalize_surface_value(value))] = canonical_key
        for alias in expected_record.get("aliases", []) or []:
            canonical_by_surface_form[(kind, _normalize_surface_value(alias))] = canonical_key
    for semantic_group in expectation.get("semantic_groups", []) or []:
        canonical = semantic_group["canonical"]
        canonical_key = (str(canonical["kind"]), str(canonical["value"]))
        canonical_by_surface_form[(canonical_key[0], _normalize_surface_value(canonical_key[1]))] = canonical_key
        for equivalent_value in semantic_group.get("equivalent_values", []) or []:
            canonical_by_surface_form[(canonical_key[0], _normalize_surface_value(equivalent_value))] = canonical_key
    return canonical_by_surface_form


def _build_umbrella_mappings(expectation: dict[str, Any]) -> dict[str, set[tuple[str, str]]]:
    umbrella_mappings: dict[str, set[tuple[str, str]]] = {}
    for umbrella_mapping in expectation.get("umbrella_mappings", []) or []:
        umbrella_value = _normalize_surface_value(umbrella_mapping["umbrella_value"])
        umbrella_mappings[umbrella_value] = {
            (str(concept_record["kind"]), str(concept_record["value"]))
            for concept_record in umbrella_mapping.get("maps_to", []) or []
        }
    return umbrella_mappings


def _normalize_surface_value(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")
