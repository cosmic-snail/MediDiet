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
    raw_extracted_concept_keys: set[tuple[str, str]] = set()
    structured_polarity_pairs: list[dict[str, Any]] = []
    for extracted_rule in extracted_rules:
        for concept_record in extracted_rule.get("suggested_concepts", []) or []:
            if isinstance(concept_record, dict):
                kind = str(concept_record.get("kind") or concept_record.get("suggested_kind") or "nutrition_tag")
                raw_value = str(concept_record.get("suggested_code") or concept_record.get("value") or "")
            else:
                kind = "nutrition_tag"
                raw_value = str(concept_record)
            normalized_value = _normalize_surface_value(raw_value)
            raw_extracted_concept_keys.add((kind, normalized_value))
            matched_key_for_relations = canonical_by_surface_form.get((kind, normalized_value), (kind, normalized_value))
            if isinstance(concept_record, dict):
                for parent_concept in concept_record.get("parent_concepts", []) or []:
                    parent_value = _normalize_surface_value(parent_concept)
                    if parent_value in umbrella_mappings:
                        umbrella_covered_keys.add(matched_key_for_relations)
                structured_polarity_pairs.extend(
                    _structured_polarity_pairs(
                        source_key=matched_key_for_relations,
                        related_concepts=concept_record.get("related_concepts", []) or [],
                    )
                )
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
    surface_discovery = _evaluate_surface_discovery(
        expected_concept_keys=expected_concept_keys,
        extracted_concept_keys=raw_extracted_concept_keys,
        strict_matched_concept_keys=true_positive_keys,
    )
    polarity_mapping = _evaluate_polarity_mapping(
        expected_concept_keys=expected_concept_keys,
        extracted_concept_keys=raw_extracted_concept_keys,
        structured_polarity_pairs=structured_polarity_pairs,
    )

    return {
        "gold_id": expectation.get("gold_id"),
        "doc_id": expectation.get("doc_id"),
        "track": "concept_discovery",
        "overall": "match" if not false_negative_keys else "miss",
        "raw_suggested_concepts": _sorted_concepts(raw_extracted_concept_keys),
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
        "surface_discovery": surface_discovery,
        "polarity_mapping": polarity_mapping,
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
    surface_expected_count = sum(
        int((evaluation.get("surface_discovery") or {}).get("expected_count", 0)) for evaluation in evaluations
    )
    surface_discovered_count = sum(
        int((evaluation.get("surface_discovery") or {}).get("discovered_count", 0)) for evaluation in evaluations
    )
    surface_missing_count = sum(
        int((evaluation.get("surface_discovery") or {}).get("missing_count", 0)) for evaluation in evaluations
    )
    polarity_mapped_pairs = [
        mapped_pair
        for evaluation in evaluations
        for mapped_pair in (evaluation.get("polarity_mapping") or {}).get("mapped_pairs", []) or []
    ]
    return {
        "atomic": precision_recall_f1_for_concepts(evaluations),
        "surface_discovery": {
            "expected_count": surface_expected_count,
            "discovered_count": surface_discovered_count,
            "missing_count": surface_missing_count,
            "recall": surface_discovered_count / surface_expected_count if surface_expected_count else 0.0,
        },
        "polarity_mapping": {
            "mapped_count": len(polarity_mapped_pairs),
            "mapped_pairs": polarity_mapped_pairs,
        },
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


def _evaluate_surface_discovery(
    *,
    expected_concept_keys: set[tuple[str, str]],
    extracted_concept_keys: set[tuple[str, str]],
    strict_matched_concept_keys: set[tuple[str, str]],
) -> dict[str, Any]:
    discovered_records: list[dict[str, Any]] = []
    discovered_expected_keys: set[tuple[str, str]] = set()
    for expected_key in sorted(expected_concept_keys):
        if expected_key in strict_matched_concept_keys:
            discovered_expected_keys.add(expected_key)
            discovered_records.append(
                {
                    "expected": _concept_record(expected_key),
                    "surface": _concept_record(expected_key),
                    "match_type": "canonical",
                }
            )
            continue
        surface_match = _best_surface_match(expected_key, extracted_concept_keys)
        if surface_match is not None:
            discovered_expected_keys.add(expected_key)
            discovered_records.append(
                {
                    "expected": _concept_record(expected_key),
                    "surface": _concept_record(surface_match),
                    "match_type": _surface_match_type(expected_key, surface_match),
                }
            )
    missing_keys = expected_concept_keys - discovered_expected_keys
    return {
        "expected_count": len(expected_concept_keys),
        "discovered_count": len(discovered_expected_keys),
        "missing_count": len(missing_keys),
        "recall": len(discovered_expected_keys) / len(expected_concept_keys) if expected_concept_keys else 0.0,
        "discovered_concepts": discovered_records,
        "missing_concepts": _sorted_concepts(missing_keys),
    }


def _evaluate_polarity_mapping(
    *,
    expected_concept_keys: set[tuple[str, str]],
    extracted_concept_keys: set[tuple[str, str]],
    structured_polarity_pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mapped_pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str, str, str, str]] = set()
    for structured_pair in structured_polarity_pairs or []:
        expected_record = structured_pair.get("expected", {})
        surface_record = structured_pair.get("surface", {})
        expected_key = (str(expected_record.get("kind", "")), str(expected_record.get("value", "")))
        if expected_key not in expected_concept_keys:
            continue
        pair_key = (
            expected_key[0],
            expected_key[1],
            str(surface_record.get("kind", "")),
            str(surface_record.get("value", "")),
            str(structured_pair.get("relation", "")),
        )
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        mapped_pairs.append(structured_pair)
    for expected_key in sorted(expected_concept_keys):
        for extracted_key in sorted(extracted_concept_keys):
            if not _is_polarity_pair(expected_key, extracted_key):
                continue
            pair_key = (expected_key[0], expected_key[1], extracted_key[0], extracted_key[1], "avoid_high_to_prefer_low")
            if pair_key in seen_pairs:
                break
            seen_pairs.add(pair_key)
            mapped_pairs.append(
                {
                    "expected": _concept_record(expected_key),
                    "surface": _concept_record(extracted_key),
                    "relation": "avoid_high_to_prefer_low",
                }
            )
            break
    return {"mapped_count": len(mapped_pairs), "mapped_pairs": mapped_pairs}


def _structured_polarity_pairs(
    *,
    source_key: tuple[str, str],
    related_concepts: list[Any],
) -> list[dict[str, Any]]:
    mapped_pairs: list[dict[str, Any]] = []
    for related_concept in related_concepts:
        if not isinstance(related_concept, dict) or related_concept.get("relation") != "polarity_pair":
            continue
        target_value = _normalize_surface_value(related_concept.get("target", ""))
        if not target_value:
            continue
        mapped_pairs.append(
            {
                "expected": _concept_record(source_key),
                "surface": {"kind": "contraindication", "value": target_value},
                "relation": "polarity_pair",
            }
        )
    return mapped_pairs


def _best_surface_match(
    expected_key: tuple[str, str],
    extracted_concept_keys: set[tuple[str, str]],
) -> tuple[str, str] | None:
    polarity_matches = [
        extracted_key for extracted_key in sorted(extracted_concept_keys) if _is_polarity_pair(expected_key, extracted_key)
    ]
    if polarity_matches:
        return polarity_matches[0]
    expected_tokens = _semantic_concept_tokens(expected_key[1])
    for extracted_key in sorted(extracted_concept_keys):
        extracted_tokens = _semantic_concept_tokens(extracted_key[1])
        if expected_tokens & extracted_tokens:
            return extracted_key
    return None


def _surface_match_type(expected_key: tuple[str, str], extracted_key: tuple[str, str]) -> str:
    if _is_polarity_pair(expected_key, extracted_key):
        return "polarity_pair"
    return "token_overlap"


def _is_polarity_pair(expected_key: tuple[str, str], extracted_key: tuple[str, str]) -> bool:
    expected_tokens = _concept_tokens(expected_key[1])
    extracted_tokens = _concept_tokens(extracted_key[1])
    return "low" in expected_tokens and "high" in extracted_tokens and bool(
        (expected_tokens - {"low"}) & (extracted_tokens - {"high", "food", "foods"})
    )


def _concept_tokens(value: str) -> set[str]:
    ignored_tokens = {"support", "management", "restriction", "restricted", "limited", "limit", "control", "controlled"}
    return {token for token in _normalize_surface_value(value).split("_") if token and token not in ignored_tokens}


def _semantic_concept_tokens(value: str) -> set[str]:
    return _concept_tokens(value) - {"high", "low", "avoid", "prefer"}


def _concept_record(key: tuple[str, str]) -> dict[str, str]:
    return {"kind": key[0], "value": key[1]}


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
