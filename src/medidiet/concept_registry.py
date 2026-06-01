from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Iterable

from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry


class ConceptSourceType(str, Enum):
    MANUAL = "manual"
    LLM = "llm"


class ConceptStatus(str, Enum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


DEFAULT_PRODUCT_CONCEPT_STATUSES = (ConceptStatus.APPROVED,)
EXPERIMENT_CONCEPT_STATUSES = (ConceptStatus.APPROVED, ConceptStatus.CANDIDATE)


def load_concept_definitions_from_jsonl(
    path: Path,
    *,
    include_statuses: Iterable[ConceptStatus | str] = DEFAULT_PRODUCT_CONCEPT_STATUSES,
) -> list[ConceptDefinition]:
    if not path.exists():
        return []
    allowed_statuses = _normalize_statuses(include_statuses)
    definitions: list[ConceptDefinition] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        concept_record = json.loads(line)
        status = ConceptStatus(str(concept_record.get("status", "")))
        if status not in allowed_statuses:
            continue
        source_type = ConceptSourceType(str(concept_record.get("source_type", ConceptSourceType.MANUAL.value)))
        kind = CodeKind(str(concept_record["kind"]))
        value = str(concept_record["value"])
        definitions.append(
            ConceptDefinition(
                code=ConceptCode(kind, value),
                display_name=str(concept_record.get("display_name") or value.replace("_", " ").title()),
                aliases=tuple(str(alias) for alias in concept_record.get("aliases", []) or []),
                source=source_type.value,
            )
        )
    return definitions


def merge_concept_definitions(
    base_registry: ConceptRegistry,
    extra_definitions: Iterable[ConceptDefinition],
) -> ConceptRegistry:
    definitions = list(base_registry._definitions.values())
    seen = {(definition.code.kind, definition.code.value) for definition in definitions}
    for concept_definition in extra_definitions:
        key = (concept_definition.code.kind, concept_definition.code.value)
        if key in seen:
            continue
        definitions.append(concept_definition)
        seen.add(key)
    return ConceptRegistry(definitions)


def _normalize_statuses(statuses: Iterable[ConceptStatus | str]) -> set[ConceptStatus]:
    return {status if isinstance(status, ConceptStatus) else ConceptStatus(str(status)) for status in statuses}
