from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry


@dataclass(frozen=True)
class ConceptCanonicalizationResult:
    canonicalized_concepts: list[dict[str, Any]]
    delta_candidates: list[dict[str, Any]]
    summary: dict[str, int]


def canonicalize_suggested_concepts(
    suggested_concepts: list[dict[str, Any]],
    registry: ConceptRegistry,
) -> ConceptCanonicalizationResult:
    alias_index = _build_alias_index(registry)
    registry_codes = set(alias_index.values())
    canonicalized_concepts: list[dict[str, Any]] = []
    delta_candidates: list[dict[str, Any]] = []
    polarity_pair_count = 0

    for suggested_concept in suggested_concepts:
        raw_kind = CodeKind(str(suggested_concept.get("kind", CodeKind.NUTRITION_TAG.value)))
        raw_value = str(suggested_concept.get("suggested_code") or suggested_concept.get("value") or "")
        candidate_surfaces = _candidate_surfaces(suggested_concept, raw_value)
        canonical_code, match_type = _match_canonical_code(raw_kind, candidate_surfaces, alias_index)
        needs_review = False
        if canonical_code is None:
            canonical_code = ConceptCode(raw_kind, _normalize_concept_value(raw_value))
            match_type = "new_candidate"
            needs_review = True
            delta_candidates.append(_build_delta_candidate(suggested_concept, canonical_code))

        canonicalized_concept = {
            **suggested_concept,
            "raw_suggested_code": raw_value,
            "suggested_code": canonical_code.value,
            "kind": canonical_code.kind.value,
            "canonicalization": {
                "match_type": match_type,
                "needs_review": needs_review,
            },
        }
        related_concepts = list(canonicalized_concept.get("related_concepts", []) or [])
        polarity_target = _polarity_pair_target(canonical_code, registry_codes)
        if polarity_target is not None and not _has_relation(related_concepts, polarity_target):
            related_concepts.append({"target": polarity_target.value, "relation": "polarity_pair"})
        if related_concepts:
            canonicalized_concept["related_concepts"] = related_concepts
            polarity_pair_count += sum(1 for relation in related_concepts if relation.get("relation") == "polarity_pair")
        for parent_concept in canonicalized_concept.get("parent_concepts", []) or []:
            delta_candidates.append(
                _build_contains_relation_delta(
                    parent_concept=parent_concept,
                    child_code=canonical_code,
                    suggested_concept=suggested_concept,
                )
            )
        canonicalized_concepts.append(canonicalized_concept)

    canonicalized_count = sum(
        1
        for concept_record in canonicalized_concepts
        if concept_record["canonicalization"]["match_type"] != "new_candidate"
    )
    return ConceptCanonicalizationResult(
        canonicalized_concepts=canonicalized_concepts,
        delta_candidates=delta_candidates,
        summary={
            "input_count": len(suggested_concepts),
            "canonicalized_count": canonicalized_count,
            "new_candidate_count": len(delta_candidates),
            "polarity_pair_count": polarity_pair_count,
        },
    )


def _build_alias_index(registry: ConceptRegistry) -> dict[tuple[CodeKind, str], ConceptCode]:
    alias_index: dict[tuple[CodeKind, str], ConceptCode] = {}
    for definition in _registry_definitions(registry):
        surfaces = [
            definition.code.value,
            definition.display_name,
            *definition.aliases,
        ]
        for surface in surfaces:
            alias_index[(definition.code.kind, _normalize_surface_value(surface))] = definition.code
    return alias_index


def _registry_definitions(registry: ConceptRegistry) -> list[ConceptDefinition]:
    return list(registry._definitions.values())


def _candidate_surfaces(suggested_concept: dict[str, Any], raw_value: str) -> list[str]:
    surfaces = [
        raw_value,
        str(suggested_concept.get("display_name") or ""),
        str(suggested_concept.get("definition") or ""),
    ]
    surfaces.extend(str(alias) for alias in suggested_concept.get("aliases", []) or [])
    return [surface for surface in surfaces if surface]


def _match_canonical_code(
    kind: CodeKind,
    candidate_surfaces: list[str],
    alias_index: dict[tuple[CodeKind, str], ConceptCode],
) -> tuple[ConceptCode | None, str]:
    for surface in candidate_surfaces:
        normalized_surface = _normalize_surface_value(surface)
        code = alias_index.get((kind, normalized_surface))
        if code is not None:
            match_type = "exact" if normalized_surface == code.value else "alias"
            return code, match_type
    return None, "new_candidate"


def _polarity_pair_target(
    canonical_code: ConceptCode,
    registry_codes: set[ConceptCode],
) -> ConceptCode | None:
    if canonical_code.kind is not CodeKind.CONTRAINDICATION:
        return None
    if not canonical_code.value.startswith("high_"):
        return None
    low_value = "low_" + canonical_code.value.removeprefix("high_")
    candidates = [
        low_value,
        low_value.removesuffix("_foods"),
        low_value.removesuffix("_food"),
    ]
    for candidate_value in candidates:
        candidate_code = ConceptCode(CodeKind.NUTRITION_TAG, candidate_value)
        if candidate_code in registry_codes:
            return candidate_code
    return None


def _has_relation(related_concepts: list[dict[str, str]], target_code: ConceptCode) -> bool:
    return any(
        relation.get("target") == target_code.value and relation.get("relation") == "polarity_pair"
        for relation in related_concepts
    )


def _build_delta_candidate(
    suggested_concept: dict[str, Any],
    canonical_code: ConceptCode,
) -> dict[str, Any]:
    return {
        "action": "add_concept",
        "kind": canonical_code.kind.value,
        "value": canonical_code.value,
        "display_name": str(suggested_concept.get("display_name") or canonical_code.value.replace("_", " ").title()),
        "aliases": list(suggested_concept.get("aliases", []) or []),
        "evidence_quotes": list(suggested_concept.get("evidence_quotes", []) or []),
        "status": "candidate",
        "source": "hybrid_canonicalizer",
    }


def _build_contains_relation_delta(
    *,
    parent_concept: str,
    child_code: ConceptCode,
    suggested_concept: dict[str, Any],
) -> dict[str, Any]:
    return {
        "action": "add_relation",
        "relation": "contains",
        "source": _normalize_concept_value(parent_concept),
        "target_kind": child_code.kind.value,
        "target": child_code.value,
        "evidence_quotes": list(suggested_concept.get("evidence_quotes", []) or []),
        "status": "candidate",
        "source_type": "hybrid_canonicalizer",
    }


def _normalize_concept_value(value: str) -> str:
    normalized = _normalize_surface_value(value)
    if not normalized:
        return "unknown_concept"
    if re.fullmatch(r"[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?", normalized):
        return normalized
    return "concept_" + normalized


def _normalize_surface_value(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized
