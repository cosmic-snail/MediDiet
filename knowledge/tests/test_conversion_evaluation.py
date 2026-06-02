from knowledge.conversion_evaluation import evaluate_conversion_expectation


def test_evaluate_percent_energy_to_grams_conversion():
    expectation = {
        "gold_id": "gold-sugar",
        "source_expression": {"metric": "free_sugars_percent_energy", "max_value": 10, "scope": "daily"},
        "target_expression": {"metric": "sugar_g", "max_value": 50, "scope": "daily"},
        "required_assumptions": [
            {"name": "energy_reference_kcal", "value": 2000, "source": "benchmark_assumption"},
            {"name": "sugar_kcal_per_g", "value": 4, "source": "nutrition_conversion_constant"},
        ],
    }
    extracted_conversion = {
        "source_metric": "free_sugars_percent_energy",
        "target_metric": "sugar_g",
        "source_value": 10,
        "target_value": 50,
        "assumptions": {"energy_reference_kcal": 2000, "sugar_kcal_per_g": 4},
    }

    evaluation = evaluate_conversion_expectation(expectation, extracted_conversion)

    assert evaluation["overall"] == "match"
    assert evaluation["value_error"] == 0


def test_conversion_requires_explicit_assumptions():
    expectation = {
        "gold_id": "gold-sugar",
        "source_expression": {"metric": "free_sugars_percent_energy", "max_value": 10, "scope": "daily"},
        "target_expression": {"metric": "sugar_g", "max_value": 50, "scope": "daily"},
        "required_assumptions": [
            {"name": "energy_reference_kcal", "value": 2000, "source": "benchmark_assumption"},
            {"name": "sugar_kcal_per_g", "value": 4, "source": "nutrition_conversion_constant"},
        ],
    }
    extracted_conversion = {
        "source_metric": "free_sugars_percent_energy",
        "target_metric": "sugar_g",
        "source_value": 10,
        "target_value": 50,
        "assumptions": {"sugar_kcal_per_g": 4},
    }

    evaluation = evaluate_conversion_expectation(expectation, extracted_conversion)

    assert evaluation["overall"] == "miss"
    assert evaluation["missing_assumptions"] == ["energy_reference_kcal"]
