from datetime import datetime, timedelta, timezone
import unittest

from medidiet.domain import CodeKind, Confidence, DataSource, IntakeRecord, Nutrients
from medidiet.nutrition import DailyNutritionCalculator, NutritionReason
from medidiet.rules import LimitScope, NutrientMetric, load_baseline_rule_pack


NOW = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def intake(food_label, hours_ago, nutrients, confidence=0.9):
    return IntakeRecord(
        food_label=food_label,
        occurred_at=NOW - timedelta(hours=hours_ago),
        meal_label="snack",
        portion="one serving",
        nutrients=nutrients,
        confidence=Confidence(confidence),
        source=DataSource.SYSTEM_ESTIMATED,
    )


class NutritionCalculatorTest(unittest.TestCase):
    def setUp(self):
        self.pack = load_baseline_rule_pack()
        self.calculator = DailyNutritionCalculator(self.pack, now=NOW)

    def test_aggregates_daily_totals_with_float_values(self):
        records = [
            intake("breakfast", 5, Nutrients(energy_kcal=300.5, sodium_mg=420.25, sugar_g=6.5, carbs_g=30.25)),
            intake("lunch", 1, Nutrients(energy_kcal=330.25, sodium_mg=500.5, sugar_g=8.25, carbs_g=40.5)),
        ]

        state = self.calculator.aggregate(records)

        self.assertAlmostEqual(state.total.energy_kcal, 630.75)
        self.assertAlmostEqual(state.total.sodium_mg, 920.75)
        self.assertAlmostEqual(state.total.sugar_g, 14.75)
        self.assertAlmostEqual(state.total.carbs_g, 70.75)

    def test_low_confidence_records_are_reported_but_still_counted(self):
        records = [
            intake("photo-estimated dessert", 1, Nutrients(sugar_g=10), confidence=0.4),
        ]

        state = self.calculator.aggregate(records)

        self.assertEqual(state.low_confidence_labels, ("photo-estimated dessert",))
        self.assertEqual(state.total.sugar_g, 10)

    def test_next_meal_target_uses_concept_tags_not_strings(self):
        diabetes = self.pack.concepts.require(CodeKind.CONDITION, "diabetes")

        target = self.calculator.next_meal_target({diabetes}, [])

        controlled_carbs = self.pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs")
        self.assertIn(controlled_carbs, target.preferred_tags)
        self.assertTrue(all(tag.kind is CodeKind.NUTRITION_TAG for tag in target.preferred_tags))
        self.assertFalse(any(isinstance(tag, str) for tag in target.preferred_tags))

    def test_daily_sugar_limit_uses_remaining_allowance(self):
        diabetes = self.pack.concepts.require(CodeKind.CONDITION, "diabetes")
        records = [
            intake("sweet yogurt", 2, Nutrients(sugar_g=18)),
        ]

        target = self.calculator.next_meal_target({diabetes}, records)

        daily_limit = target.find_limit(NutrientMetric.SUGAR_G, LimitScope.DAILY)
        self.assertEqual(daily_limit.limit_value, 25)
        self.assertEqual(daily_limit.consumed_value, 18)
        self.assertEqual(daily_limit.remaining_value, 7)
        self.assertEqual(daily_limit.reason, NutritionReason.DAILY_LIMIT_REMAINING)

    def test_rolling_sugar_limit_counts_only_records_inside_window(self):
        diabetes = self.pack.concepts.require(CodeKind.CONDITION, "diabetes")
        records = [
            intake("recent sweet drink", 1, Nutrients(sugar_g=9)),
            intake("old sweet drink", 5, Nutrients(sugar_g=12)),
        ]

        target = self.calculator.next_meal_target({diabetes}, records)

        rolling_limit = target.find_limit(NutrientMetric.SUGAR_G, LimitScope.ROLLING_WINDOW)
        self.assertEqual(rolling_limit.limit_value, 15)
        self.assertEqual(rolling_limit.window_hours, 4)
        self.assertEqual(rolling_limit.consumed_value, 9)
        self.assertEqual(rolling_limit.remaining_value, 6)
        self.assertEqual(rolling_limit.reason, NutritionReason.ROLLING_LIMIT_REMAINING)

    def test_per_meal_limit_is_carried_without_daily_consumption(self):
        hypertension = self.pack.concepts.require(CodeKind.CONDITION, "hypertension")

        target = self.calculator.next_meal_target({hypertension}, [])

        sodium_limit = target.find_limit(NutrientMetric.SODIUM_MG, LimitScope.PER_MEAL)
        self.assertEqual(sodium_limit.limit_value, 700)
        self.assertEqual(sodium_limit.consumed_value, 0)
        self.assertEqual(sodium_limit.remaining_value, 700)
        self.assertEqual(sodium_limit.reason, NutritionReason.PER_MEAL_LIMIT)


if __name__ == "__main__":
    unittest.main()
