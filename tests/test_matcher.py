import unittest

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    Confidence,
    DataSource,
    MealLabel,
    MenuItem,
    Nutrients,
    Preference,
)
from medidiet.matcher import MatchRejectionCode, MenuMatcher
from medidiet.nutrition import NutritionReason, RemainingNutrientLimit
from medidiet.planner import MealPlan
from medidiet.rules import LimitScope, NutrientMetric, load_baseline_rule_pack


def item(
    pack,
    item_id,
    *,
    nutrition_tags=(),
    contraindication_tags=(),
    taste_tags=(),
    sodium=450,
    sugar=5,
    price=3000,
    distance=800,
    reliability=0.9,
    available=True,
):
    return MenuItem(
        item_id=item_id,
        merchant_id="shop",
        name=item_id,
        ingredients={ConceptCode(CodeKind.INGREDIENT, "fish")},
        allergens=set(),
        taste_tags={ConceptCode(CodeKind.TASTE_TAG, tag) for tag in taste_tags},
        nutrition_tags={pack.concepts.require(CodeKind.NUTRITION_TAG, tag) for tag in nutrition_tags},
        contraindication_tags={pack.concepts.require(CodeKind.CONTRAINDICATION, tag) for tag in contraindication_tags},
        nutrients=Nutrients(energy_kcal=520, carbs_g=45, protein_g=32, fat_g=16, sodium_mg=sodium, sugar_g=sugar, fiber_g=5),
        nutrition_confidence=Confidence(0.9),
        source=DataSource.MERCHANT_LABEL,
        price_cents=price,
        distance_meters=distance,
        merchant_reliability=reliability,
        available=available,
    )


class MenuMatcherTest(unittest.TestCase):
    def setUp(self):
        self.pack = load_baseline_rule_pack()
        self.matcher = MenuMatcher()

    def test_excludes_avoid_tags_with_integer_rejection_code(self):
        plan = MealPlan(
            meal_label=MealLabel.DINNER,
            required_tags=frozenset({self.pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium")}),
            avoid_tags=frozenset({self.pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium")}),
        )
        candidates = [
            item(self.pack, "safe", nutrition_tags=("low_sodium",)),
            item(self.pack, "salty", contraindication_tags=("high_sodium",)),
        ]

        result = self.matcher.match(plan, candidates, Preference())

        self.assertEqual([score.item.item_id for score in result.accepted], ["safe"])
        rejection = result.excluded["salty"]
        self.assertEqual(rejection.code, MatchRejectionCode.AVOID_TAG)
        self.assertIsInstance(rejection.code.value, int)
        self.assertNotIsInstance(rejection.code.value, float)
        self.assertEqual(rejection.concept, self.pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium"))

    def test_excludes_items_exceeding_per_meal_nutrient_limit(self):
        sodium_limit = RemainingNutrientLimit(
            metric=NutrientMetric.SODIUM_MG,
            scope=LimitScope.PER_MEAL,
            limit_value=700,
            consumed_value=0,
            remaining_value=700,
            reason=NutritionReason.PER_MEAL_LIMIT,
        )
        plan = MealPlan(meal_label=MealLabel.DINNER, limits=(sodium_limit,))
        candidates = [
            item(self.pack, "safe", sodium=500),
            item(self.pack, "too-salty", sodium=900),
        ]

        result = self.matcher.match(plan, candidates, Preference())

        self.assertEqual([score.item.item_id for score in result.accepted], ["safe"])
        rejection = result.excluded["too-salty"]
        self.assertEqual(rejection.code, MatchRejectionCode.NUTRIENT_LIMIT_EXCEEDED)
        self.assertEqual(rejection.metric, NutrientMetric.SODIUM_MG)
        self.assertEqual(rejection.scope, LimitScope.PER_MEAL)
        self.assertEqual(rejection.measured_value, 900)
        self.assertEqual(rejection.limit_value, 700)

    def test_excludes_unavailable_items(self):
        result = self.matcher.match(
            MealPlan(meal_label=MealLabel.LUNCH),
            [item(self.pack, "closed", available=False)],
            Preference(),
        )

        self.assertEqual(result.excluded["closed"].code, MatchRejectionCode.UNAVAILABLE)
        self.assertEqual(result.accepted, ())

    def test_ranks_safe_items_by_tags_preference_price_distance_and_reliability(self):
        plan = MealPlan(
            meal_label=MealLabel.DINNER,
            required_tags=frozenset(
                {
                    self.pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"),
                    self.pack.concepts.require(CodeKind.NUTRITION_TAG, "vegetable_rich"),
                }
            ),
        )
        preference = Preference(
            taste_tags={ConceptCode(CodeKind.TASTE_TAG, "light")},
            max_price_cents=3500,
            max_distance_meters=1000,
        )
        candidates = [
            item(self.pack, "ok", nutrition_tags=("low_sodium",), price=4000, distance=2000, reliability=0.7),
            item(
                self.pack,
                "best",
                nutrition_tags=("low_sodium", "vegetable_rich"),
                taste_tags=("light",),
                price=2800,
                distance=600,
                reliability=0.95,
            ),
        ]

        result = self.matcher.match(plan, candidates, preference)

        self.assertEqual([score.item.item_id for score in result.accepted], ["best", "ok"])
        self.assertGreater(result.accepted[0].score, result.accepted[1].score)

    # ------------------------------------------------------------------
    # Phase 3: Ingredient diversity scoring tests
    # ------------------------------------------------------------------

    def test_recent_ingredients_default_empty_has_no_effect(self):
        """Default empty recent_ingredients does not change scoring."""
        plan = MealPlan(meal_label=MealLabel.DINNER)
        candidates = [item(self.pack, "meal")]
        result = self.matcher.match(plan, candidates, Preference())
        self.assertEqual(len(result.accepted), 1)

    def test_repeated_ingredient_penalty_reduces_score(self):
        """Item with repeated ingredients scores lower."""
        fish = ConceptCode(CodeKind.INGREDIENT, "fish")
        plan = MealPlan(meal_label=MealLabel.DINNER)
        # Create an item whose ingredient (fish) is in recent_ingredients
        meal_item = MenuItem(
            item_id="fish-meal",
            merchant_id="shop",
            name="fish-meal",
            ingredients={fish},
            allergens=set(),
            taste_tags=set(),
            nutrition_tags=set(),
            contraindication_tags=set(),
            nutrients=Nutrients(energy_kcal=500, carbs_g=40, protein_g=30, fat_g=15, sodium_mg=400, sugar_g=5, fiber_g=3),
            nutrition_confidence=Confidence(0.9),
            source=DataSource.MERCHANT_LABEL,
            price_cents=3000,
            distance_meters=800,
            merchant_reliability=0.9,
        )
        # Same item scored without recent_ingredients
        result_no_penalty = self.matcher.match(plan, [meal_item], Preference(), recent_ingredients=frozenset())
        # Same item scored with fish in recent_ingredients → -1 penalty
        result_with_penalty = self.matcher.match(
            plan, [meal_item], Preference(), recent_ingredients=frozenset({fish})
        )
        self.assertEqual(len(result_no_penalty.accepted), 1)
        self.assertEqual(len(result_with_penalty.accepted), 1)
        self.assertGreater(
            result_no_penalty.accepted[0].score,
            result_with_penalty.accepted[0].score,
        )

    def test_multiple_repeated_ingredients_accumulate_penalty(self):
        """Each repeated ingredient adds -1 to the score."""
        fish = ConceptCode(CodeKind.INGREDIENT, "fish")
        vegetable = ConceptCode(CodeKind.INGREDIENT, "vegetable")
        plan = MealPlan(meal_label=MealLabel.DINNER)
        meal_item = MenuItem(
            item_id="combo",
            merchant_id="shop",
            name="combo",
            ingredients={fish, vegetable},
            allergens=set(),
            taste_tags=set(),
            nutrition_tags=set(),
            contraindication_tags=set(),
            nutrients=Nutrients(energy_kcal=500, carbs_g=40, protein_g=30, fat_g=15, sodium_mg=400, sugar_g=5, fiber_g=3),
            nutrition_confidence=Confidence(0.9),
            source=DataSource.MERCHANT_LABEL,
            price_cents=3000,
            distance_meters=800,
            merchant_reliability=0.9,
        )

        result_no_penalty = self.matcher.match(plan, [meal_item], Preference(), recent_ingredients=frozenset())
        result_one_penalty = self.matcher.match(
            plan, [meal_item], Preference(), recent_ingredients=frozenset({fish})
        )
        result_two_penalty = self.matcher.match(
            plan, [meal_item], Preference(), recent_ingredients=frozenset({fish, vegetable})
        )

        score_none = result_no_penalty.accepted[0].score
        score_one = result_one_penalty.accepted[0].score
        score_two = result_two_penalty.accepted[0].score
        # Each penalty = -1
        self.assertAlmostEqual(score_one, score_none - 1.0)
        self.assertAlmostEqual(score_two, score_none - 2.0)


if __name__ == "__main__":
    unittest.main()
