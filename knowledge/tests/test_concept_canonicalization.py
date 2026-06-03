from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry

from knowledge.concept_canonicalization import canonicalize_suggested_concepts


def test_alias_match_canonicalizes_suggested_concept_without_losing_raw_value():
    registry = ConceptRegistry(
        [
            ConceptDefinition(
                ConceptCode(CodeKind.NUTRITION_TAG, "hydration_support"),
                "Hydration support",
                aliases=("adequate hydration", "fluid intake"),
            )
        ]
    )
    suggestions = [
        {
            "kind": "nutrition_tag",
            "suggested_code": "adequate_hydration",
            "display_name": "Adequate Hydration",
            "aliases": ["fluid intake"],
            "evidence_quotes": ["Drink enough fluids."],
        }
    ]

    result = canonicalize_suggested_concepts(suggestions, registry)

    assert result.summary["canonicalized_count"] == 1
    canonicalized = result.canonicalized_concepts[0]
    assert canonicalized["suggested_code"] == "hydration_support"
    assert canonicalized["raw_suggested_code"] == "adequate_hydration"
    assert canonicalized["canonicalization"]["match_type"] == "alias"
    assert canonicalized["canonicalization"]["needs_review"] is False


def test_polarity_match_links_high_contraindication_to_low_preferred_concept():
    registry = ConceptRegistry(
        [
            ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "low_purine"), "Low purine"),
            ConceptDefinition(
                ConceptCode(CodeKind.CONTRAINDICATION, "high_purine_food"),
                "High purine food",
                aliases=("high purine foods",),
            ),
        ]
    )
    suggestions = [
        {
            "kind": "contraindication",
            "suggested_code": "high_purine_foods",
            "display_name": "High Purine Foods",
            "polarity": "avoid",
        }
    ]

    result = canonicalize_suggested_concepts(suggestions, registry)

    canonicalized = result.canonicalized_concepts[0]
    assert canonicalized["suggested_code"] == "high_purine_food"
    assert canonicalized["related_concepts"] == [
        {"target": "low_purine", "relation": "polarity_pair"}
    ]
    assert canonicalized["canonicalization"]["match_type"] == "alias"
    assert result.summary["polarity_pair_count"] == 1


def test_unmatched_concept_becomes_registry_delta_candidate():
    registry = ConceptRegistry([])
    suggestions = [
        {
            "kind": "contraindication",
            "suggested_code": "fructose_sweetened_drinks",
            "display_name": "Fructose sweetened drinks",
            "aliases": ["sweetened drinks"],
            "evidence_quotes": ["Be careful with sweetened drinks."],
        }
    ]

    result = canonicalize_suggested_concepts(suggestions, registry)

    canonicalized = result.canonicalized_concepts[0]
    assert canonicalized["suggested_code"] == "fructose_sweetened_drinks"
    assert canonicalized["canonicalization"]["match_type"] == "new_candidate"
    assert canonicalized["canonicalization"]["needs_review"] is True
    assert result.delta_candidates == [
        {
            "action": "add_concept",
            "kind": "contraindication",
            "value": "fructose_sweetened_drinks",
            "display_name": "Fructose sweetened drinks",
            "aliases": ["sweetened drinks"],
            "evidence_quotes": ["Be careful with sweetened drinks."],
            "status": "candidate",
            "source": "hybrid_canonicalizer",
        }
    ]


def test_parent_concept_generates_contains_relation_delta_candidate():
    registry = ConceptRegistry(
        [
            ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "low_purine"), "Low purine"),
        ]
    )
    suggestions = [
        {
            "kind": "nutrition_tag",
            "suggested_code": "low_purine",
            "parent_concepts": ["gout_diet"],
            "evidence_quotes": ["Gout diet advice includes low-purine eating."],
        }
    ]

    result = canonicalize_suggested_concepts(suggestions, registry)

    assert result.delta_candidates == [
        {
            "action": "add_relation",
            "relation": "contains",
            "source": "gout_diet",
            "target_kind": "nutrition_tag",
            "target": "low_purine",
            "evidence_quotes": ["Gout diet advice includes low-purine eating."],
            "status": "candidate",
            "source_type": "hybrid_canonicalizer",
        }
    ]
