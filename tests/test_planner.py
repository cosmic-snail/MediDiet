import unittest

from medidiet.domain import CodeKind, MealLabel
from medidiet.nutrition import NextMealTarget, NutritionReason, RemainingNutrientLimit
from medidiet.planner import MealInstruction, MealPlanGenerator
from medidiet.rules import LimitScope, NutrientMetric, load_baseline_rule_pack


class MealPlanGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.pack = load_baseline_rule_pack()
        self.generator = MealPlanGenerator(self.pack)

    def test_generates_low_sodium_plan_from_per_meal_limit(self):
        target = NextMealTarget(
            limits=(
                RemainingNutrientLimit(
                    metric=NutrientMetric.SODIUM_MG,
                    scope=LimitScope.PER_MEAL,
                    limit_value=700,
                    consumed_value=0,
                    remaining_value=700,
                    reason=NutritionReason.PER_MEAL_LIMIT,
                ),
            ),
            preferred_tags=frozenset({self.pack.concepts.require(CodeKind.NUTRITION_TAG, "vegetable_rich")}),
        )

        plan = self.generator.generate(target, MealLabel.DINNER)

        self.assertEqual(plan.meal_label, MealLabel.DINNER)
        self.assertIn(self.pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"), plan.required_tags)
        self.assertIn(self.pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium"), plan.avoid_tags)
        self.assertIn(MealInstruction.AVOID_EXTRA_SAUCE, plan.instructions)
        self.assertEqual(plan.limits, target.limits)

    def test_generates_controlled_carbs_plan_from_daily_or_rolling_sugar_limits(self):
        target = NextMealTarget(
            limits=(
                RemainingNutrientLimit(
                    metric=NutrientMetric.SUGAR_G,
                    scope=LimitScope.DAILY,
                    limit_value=25,
                    consumed_value=18,
                    remaining_value=7,
                    reason=NutritionReason.DAILY_LIMIT_REMAINING,
                ),
                RemainingNutrientLimit(
                    metric=NutrientMetric.SUGAR_G,
                    scope=LimitScope.ROLLING_WINDOW,
                    limit_value=15,
                    consumed_value=9,
                    remaining_value=6,
                    reason=NutritionReason.ROLLING_LIMIT_REMAINING,
                    window_hours=4,
                ),
            ),
        )

        plan = self.generator.generate(target, MealLabel.SNACK)

        self.assertIn(self.pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"), plan.required_tags)
        self.assertIn(self.pack.concepts.require(CodeKind.CONTRAINDICATION, "sugary_drink"), plan.avoid_tags)
        self.assertIn(MealInstruction.CONTROL_ADDED_SUGAR, plan.instructions)

    def test_plan_uses_concept_codes_and_integer_instruction_enums(self):
        target = NextMealTarget(preferred_tags=frozenset({self.pack.concepts.require(CodeKind.NUTRITION_TAG, "high_fiber")}))

        plan = self.generator.generate(target, MealLabel.LUNCH)

        self.assertTrue(all(tag.kind is CodeKind.NUTRITION_TAG for tag in plan.required_tags))
        self.assertTrue(all(tag.kind is CodeKind.CONTRAINDICATION for tag in plan.avoid_tags))
        self.assertFalse(any(isinstance(tag, str) for tag in plan.required_tags))
        self.assertFalse(any(isinstance(tag, str) for tag in plan.avoid_tags))
        self.assertTrue(all(isinstance(instruction, MealInstruction) for instruction in plan.instructions))
        self.assertTrue(all(isinstance(instruction.value, int) for instruction in plan.instructions))

    def test_rejects_string_meal_label(self):
        with self.assertRaises(TypeError):
            self.generator.generate(NextMealTarget(), "dinner")


if __name__ == "__main__":
    unittest.main()
