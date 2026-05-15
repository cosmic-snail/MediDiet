import unittest

from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import (
    ConditionRule,
    LimitScope,
    NutrientLimit,
    NutrientMetric,
    load_baseline_rule_pack,
)


class RulePackTest(unittest.TestCase):
    def test_rule_pack_has_version_sources_and_registry(self):
        pack = load_baseline_rule_pack()

        self.assertEqual(pack.version, "baseline-2026-05-15")
        self.assertGreaterEqual(len(pack.sources), 4)
        self.assertEqual(pack.concepts.require(CodeKind.CONDITION, "hypertension").value, "hypertension")
        self.assertEqual(pack.concepts.require(CodeKind.CONDITION, "diabetes").value, "diabetes")

    def test_hypertension_rule_uses_table_driven_limits(self):
        pack = load_baseline_rule_pack()
        hypertension = pack.concepts.require(CodeKind.CONDITION, "hypertension")
        rule = pack.for_condition(hypertension)

        self.assertEqual(rule.condition, hypertension)
        self.assertIn(pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium"), rule.hard_exclusions)
        self.assertIn(pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"), rule.preferred_tags)
        self.assertIn(
            NutrientLimit(
                metric=NutrientMetric.SODIUM_MG,
                scope=LimitScope.PER_MEAL,
                max_value=700,
            ),
            rule.nutrition_limits,
        )

    def test_diabetes_rule_supports_daily_and_rolling_sugar_limits(self):
        pack = load_baseline_rule_pack()
        diabetes = pack.concepts.require(CodeKind.CONDITION, "diabetes")
        rule = pack.for_condition(diabetes)

        self.assertIn(pack.concepts.require(CodeKind.CONTRAINDICATION, "sugary_drink"), rule.hard_exclusions)
        self.assertIn(pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"), rule.preferred_tags)
        self.assertIn(
            NutrientLimit(
                metric=NutrientMetric.SUGAR_G,
                scope=LimitScope.DAILY,
                max_value=25,
            ),
            rule.nutrition_limits,
        )
        self.assertIn(
            NutrientLimit(
                metric=NutrientMetric.SUGAR_G,
                scope=LimitScope.ROLLING_WINDOW,
                max_value=15,
                window_hours=4,
            ),
            rule.nutrition_limits,
        )

    def test_rule_pack_rejects_unknown_or_wrong_kind_condition_lookup(self):
        pack = load_baseline_rule_pack()

        with self.assertRaises(ValueError):
            pack.for_condition(ConceptCode(CodeKind.CONDITION, "kidney_disease"))
        with self.assertRaises(TypeError):
            pack.for_condition(ConceptCode(CodeKind.ALLERGEN, "peanut"))

    def test_nutrient_limit_rejects_invalid_boundaries_and_windows(self):
        invalid_limits = [
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.DAILY, max_value=0),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.DAILY, max_value=-1),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.DAILY, max_value=float("inf")),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.DAILY, max_value=1_000_001),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.ROLLING_WINDOW, max_value=15),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.ROLLING_WINDOW, max_value=15, window_hours=0),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.DAILY, max_value=25, window_hours=24),
            dict(metric=NutrientMetric.SUGAR_G, scope=LimitScope.PER_MEAL, max_value=12, window_hours=1),
        ]

        for kwargs in invalid_limits:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    NutrientLimit(**kwargs)

    def test_condition_rule_rejects_wrong_concept_kinds(self):
        pack = load_baseline_rule_pack()
        hypertension = pack.concepts.require(CodeKind.CONDITION, "hypertension")
        low_sodium = pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium")
        high_sodium = pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium")

        with self.assertRaises(TypeError):
            ConditionRule(
                condition=low_sodium,
                hard_exclusions={high_sodium},
                preferred_tags={low_sodium},
                nutrition_limits=set(),
            )
        with self.assertRaises(TypeError):
            ConditionRule(
                condition=hypertension,
                hard_exclusions={low_sodium},
                preferred_tags={low_sodium},
                nutrition_limits=set(),
            )
        with self.assertRaises(TypeError):
            ConditionRule(
                condition=hypertension,
                hard_exclusions={high_sodium},
                preferred_tags={high_sodium},
                nutrition_limits=set(),
            )


if __name__ == "__main__":
    unittest.main()
