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


def test_evaluate_concept_expectation_counts_rule_concepts_as_discovered_atomic_values():
    expectation = {
        "gold_id": "gold-gout",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "low_purine", "aliases": []},
            {"kind": "contraindication", "value": "alcohol", "aliases": []},
        ],
    }
    extracted_rules = [
        {
            "hard_exclusions": ["alcohol"],
            "preferred_tags": ["low_purine"],
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["matched_concepts"] == [
        {"kind": "contraindication", "value": "alcohol"},
        {"kind": "nutrition_tag", "value": "low_purine"},
    ]


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


def test_evaluate_concept_expectation_reports_surface_and_polarity_diagnostics():
    expectation = {
        "gold_id": "gold-gout",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "low_purine", "aliases": ["low purine diet"]},
            {"kind": "nutrition_tag", "value": "hydration_support", "aliases": ["adequate hydration"]},
            {"kind": "contraindication", "value": "high_fructose", "aliases": ["limit fructose"]},
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {"kind": "contraindication", "suggested_code": "high_purine_food"},
                {"kind": "nutrition_tag", "suggested_code": "hydration"},
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "miss"
    assert evaluation["matched_concepts"] == []
    assert evaluation["surface_discovery"]["discovered_count"] == 2
    assert evaluation["surface_discovery"]["missing_count"] == 1
    assert evaluation["surface_discovery"]["recall"] == 2 / 3
    assert evaluation["surface_discovery"]["discovered_concepts"] == [
        {
            "expected": {"kind": "nutrition_tag", "value": "hydration_support"},
            "surface": {"kind": "nutrition_tag", "value": "hydration"},
            "match_type": "token_overlap",
        },
        {
            "expected": {"kind": "nutrition_tag", "value": "low_purine"},
            "surface": {"kind": "contraindication", "value": "high_purine_food"},
            "match_type": "polarity_pair",
        },
    ]
    assert evaluation["polarity_mapping"]["mapped_count"] == 1
    assert evaluation["polarity_mapping"]["mapped_pairs"] == [
        {
            "expected": {"kind": "nutrition_tag", "value": "low_purine"},
            "surface": {"kind": "contraindication", "value": "high_purine_food"},
            "relation": "avoid_high_to_prefer_low",
        }
    ]


def test_evaluate_concept_expectation_uses_structured_relations_from_concept_graph_metadata():
    expectation = {
        "gold_id": "gold-gout",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "low_purine", "aliases": []},
            {"kind": "contraindication", "value": "alcohol", "aliases": []},
        ],
        "do_not_score_as": ["gout_diet_context"],
        "umbrella_mappings": [
            {
                "umbrella_value": "gout_diet_context",
                "maps_to": [
                    {"kind": "nutrition_tag", "value": "low_purine"},
                    {"kind": "contraindication", "value": "alcohol"},
                ],
            }
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {
                    "kind": "nutrition_tag",
                    "suggested_code": "low_purine",
                    "parent_concepts": ["gout_diet_context"],
                    "related_concepts": [{"target": "high_purine", "relation": "polarity_pair"}],
                },
                {
                    "kind": "contraindication",
                    "suggested_code": "alcohol",
                    "parent_concepts": ["gout_diet_context"],
                },
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["umbrella_decomposition"]["coverage"] == 1.0
    assert evaluation["umbrella_decomposition"]["covered_atomic_concepts"] == [
        {"kind": "contraindication", "value": "alcohol"},
        {"kind": "nutrition_tag", "value": "low_purine"},
    ]
    assert evaluation["polarity_mapping"]["mapped_count"] == 1
    assert evaluation["polarity_mapping"]["mapped_pairs"] == [
        {
            "expected": {"kind": "nutrition_tag", "value": "low_purine"},
            "surface": {"kind": "contraindication", "value": "high_purine"},
            "relation": "polarity_pair",
        }
    ]


def test_structured_polarity_does_not_map_unrelated_target_to_management_concept():
    expectation = {
        "gold_id": "gold-ckd",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "potassium_management", "aliases": ["potassium restriction"]},
            {"kind": "nutrition_tag", "value": "phosphorus_management", "aliases": ["phosphorus restriction"]},
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {
                    "kind": "contraindication",
                    "suggested_code": "high_potassium",
                    "related_concepts": [{"target": "low_potassium", "relation": "polarity_pair"}],
                }
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["polarity_mapping"]["mapped_count"] == 0
    assert evaluation["polarity_mapping"]["mapped_pairs"] == []


def test_structured_polarity_requires_clear_low_high_opposition():
    expectation = {
        "gold_id": "gold-ckd",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "potassium_management", "aliases": ["potassium restriction"]},
            {"kind": "nutrition_tag", "value": "phosphorus_management", "aliases": ["phosphorus restriction"]},
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {
                    "kind": "nutrition_tag",
                    "suggested_code": "potassium_management",
                    "related_concepts": [{"target": "low_sodium", "relation": "polarity_pair"}],
                },
                {
                    "kind": "nutrition_tag",
                    "suggested_code": "phosphorus_management",
                    "related_concepts": [{"target": "low_sodium", "relation": "polarity_pair"}],
                },
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["polarity_mapping"]["mapped_count"] == 0
    assert evaluation["polarity_mapping"]["mapped_pairs"] == []


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
    assert summary["surface_discovery"]["recall"] == 0.0
    assert summary["polarity_mapping"]["mapped_count"] == 0
    assert summary["semantic_linking"]["linked_count"] == 2
    assert summary["semantic_linking"]["unlinked_count"] == 1
    assert summary["umbrella_decomposition"]["average_coverage"] == 0.75


def test_summarize_concept_evaluations_aggregates_surface_and_polarity_layers():
    evaluations = [
        {
            "surface_discovery": {"expected_count": 3, "discovered_count": 2, "missing_count": 1},
            "polarity_mapping": {
                "mapped_count": 1,
                "mapped_pairs": [
                    {
                        "expected": {"kind": "nutrition_tag", "value": "low_purine"},
                        "surface": {"kind": "contraindication", "value": "high_purine_food"},
                        "relation": "avoid_high_to_prefer_low",
                    }
                ],
            },
        },
        {
            "surface_discovery": {"expected_count": 2, "discovered_count": 1, "missing_count": 1},
            "polarity_mapping": {"mapped_count": 0, "mapped_pairs": []},
        },
    ]

    summary = summarize_concept_evaluations(evaluations)

    assert summary["surface_discovery"] == {
        "expected_count": 5,
        "discovered_count": 3,
        "missing_count": 2,
        "recall": 0.6,
    }
    assert summary["polarity_mapping"]["mapped_count"] == 1
