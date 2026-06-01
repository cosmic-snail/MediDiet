import json

import pytest

from medidiet.concept_registry import (
    ConceptSourceType,
    ConceptStatus,
    load_concept_definitions_from_jsonl,
    merge_concept_definitions,
)
from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry


def test_load_concept_definitions_filters_status_and_preserves_source_type(tmp_path):
    registry_path = tmp_path / "concepts.jsonl"
    registry_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "condition",
                        "value": "cardiovascular_risk",
                        "display_name": "Cardiovascular Risk",
                        "aliases": ["cardiovascular risk"],
                        "source_type": "llm",
                        "status": "candidate",
                    }
                ),
                json.dumps(
                    {
                        "kind": "condition",
                        "value": "general_population",
                        "display_name": "General Population",
                        "aliases": ["public adults"],
                        "source_type": "manual",
                        "status": "approved",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    approved_definitions = load_concept_definitions_from_jsonl(registry_path)
    experiment_definitions = load_concept_definitions_from_jsonl(
        registry_path,
        include_statuses=(ConceptStatus.APPROVED, ConceptStatus.CANDIDATE),
    )

    assert [definition.code.value for definition in approved_definitions] == ["general_population"]
    assert [definition.code.value for definition in experiment_definitions] == [
        "cardiovascular_risk",
        "general_population",
    ]
    assert approved_definitions[0].source == ConceptSourceType.MANUAL.value
    assert experiment_definitions[0].source == ConceptSourceType.LLM.value


def test_merge_concept_definitions_does_not_override_baseline():
    base_registry = ConceptRegistry(
        [
            ConceptDefinition(
                ConceptCode(CodeKind.CONDITION, "hypertension"),
                "Hypertension",
                aliases=("hypertension",),
                source="baseline",
            )
        ]
    )
    extra_definitions = [
        ConceptDefinition(
            ConceptCode(CodeKind.CONDITION, "hypertension"),
            "LLM Hypertension",
            aliases=("high blood pressure",),
            source=ConceptSourceType.LLM.value,
        ),
        ConceptDefinition(
            ConceptCode(CodeKind.CONDITION, "cardiovascular_risk"),
            "Cardiovascular Risk",
            aliases=("cardiovascular risk",),
            source=ConceptSourceType.LLM.value,
        ),
    ]

    merged_registry = merge_concept_definitions(base_registry, extra_definitions)

    assert merged_registry.require(CodeKind.CONDITION, "hypertension").value == "hypertension"
    assert merged_registry.require(CodeKind.CONDITION, "cardiovascular_risk").value == "cardiovascular_risk"
    with pytest.raises(ValueError):
        merged_registry.resolve_alias(CodeKind.CONDITION, "high blood pressure")
