from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry
from knowledge.concept_coverage import audit_concept_coverage


def test_audit_concept_coverage_reports_missing_manifest_focus():
    registry = ConceptRegistry(
        [
            ConceptDefinition(
                ConceptCode(CodeKind.CONDITION, "hypertension"),
                "Hypertension",
                aliases=("hypertension",),
            )
        ]
    )
    manifest_rows = [
        {"doc_id": "doc1", "disease_focus": ["hypertension", "cardiovascular_risk"]},
        {"doc_id": "doc2", "disease_focus": ["cardiovascular_risk"]},
    ]

    report = audit_concept_coverage(
        manifest_rows=manifest_rows,
        gold_rows=[],
        registry=registry,
    )

    assert report["condition_focus"]["registered"]["hypertension"]["count"] == 1
    assert report["condition_focus"]["missing"]["cardiovascular_risk"]["count"] == 2
    assert report["condition_focus"]["missing"]["cardiovascular_risk"]["doc_ids"] == [
        "doc1",
        "doc2",
    ]
