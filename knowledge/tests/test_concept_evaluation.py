from knowledge.concept_evaluation import (
    evaluate_concept_expectation,
    precision_recall_f1_for_concepts,
    summarize_concept_evaluations,
)


def test_evaluate_concept_expectation_matches_atomic_values_and_aliases():
    expectation = {
        "gold_id": "gold-gout",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "low_purine", "aliases": ["limit high-purine foods"]},
            {"kind": "contraindication", "value": "alcohol", "aliases": ["limit alcohol"]},
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {"kind": "nutrition_tag", "suggested_code": "limit high-purine foods"},
                {"kind": "contraindication", "suggested_code": "alcohol"},
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["matched_concepts"] == [
        {"kind": "contraindication", "value": "alcohol"},
        {"kind": "nutrition_tag", "value": "low_purine"},
    ]
    assert evaluation["missing_concepts"] == []


def test_evaluate_concept_expectation_links_same_meaning_atomic_concepts():
    expectation = {
        "gold_id": "gold-gout",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "low_purine", "aliases": ["limit high-purine foods"]},
        ],
        "semantic_groups": [
            {
                "canonical": {"kind": "nutrition_tag", "value": "low_purine"},
                "equivalent_values": ["purine_restriction", "low_purine_diet"],
            }
        ],
    }
    extracted_rules = [{"suggested_concepts": [{"kind": "nutrition_tag", "suggested_code": "purine_restriction"}]}]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["semantic_linking"]["linked_count"] == 1
    assert evaluation["semantic_linking"]["unlinked_values"] == []


def test_evaluate_concept_expectation_reports_umbrella_decomposition_separately():
    expectation = {
        "gold_id": "gold-ckd",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "potassium_management", "aliases": ["potassium restriction"]},
            {"kind": "nutrition_tag", "value": "phosphorus_management", "aliases": ["phosphorus restriction"]},
        ],
        "do_not_score_as": ["potassium_phosphorus_management"],
        "umbrella_mappings": [
            {
                "umbrella_value": "potassium_phosphorus_management",
                "maps_to": [
                    {"kind": "nutrition_tag", "value": "potassium_management"},
                    {"kind": "nutrition_tag", "value": "phosphorus_management"},
                ],
            }
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {"kind": "nutrition_tag", "suggested_code": "potassium_phosphorus_management"}
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "miss"
    assert evaluation["missing_concepts"] == [
        {"kind": "nutrition_tag", "value": "phosphorus_management"},
        {"kind": "nutrition_tag", "value": "potassium_management"},
    ]
    assert evaluation["umbrella_decomposition"]["coverage"] == 1.0
    assert evaluation["umbrella_decomposition"]["covered_atomic_concepts"] == [
        {"kind": "nutrition_tag", "value": "phosphorus_management"},
        {"kind": "nutrition_tag", "value": "potassium_management"},
    ]


def test_precision_recall_f1_for_concepts_counts_extra_atomic_concepts():
    evaluations = [
        {"true_positive_count": 2, "false_negative_count": 0, "false_positive_count": 1},
        {"true_positive_count": 1, "false_negative_count": 1, "false_positive_count": 0},
    ]

    assert precision_recall_f1_for_concepts(evaluations) == {
        "precision": 0.75,
        "recall": 0.75,
        "f1": 0.75,
    }


def test_summarize_concept_evaluations_reports_three_validation_layers():
    evaluations = [
        {
            "true_positive_count": 2,
            "false_negative_count": 1,
            "false_positive_count": 0,
            "semantic_linking": {"linked_count": 2, "unlinked_values": []},
            "umbrella_decomposition": {"coverage": 1.0},
        },
        {
            "true_positive_count": 1,
            "false_negative_count": 0,
            "false_positive_count": 1,
            "semantic_linking": {"linked_count": 0, "unlinked_values": [{"kind": "nutrition_tag", "value": "duplicate"}]},
            "umbrella_decomposition": {"coverage": 0.5},
        },
    ]

    summary = summarize_concept_evaluations(evaluations)

    assert summary["atomic"]["recall"] == 0.75
    assert summary["semantic_linking"]["linked_count"] == 2
    assert summary["semantic_linking"]["unlinked_count"] == 1
    assert summary["umbrella_decomposition"]["average_coverage"] == 0.75
