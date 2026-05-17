from datetime import datetime, timezone
import json
import unittest

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    Confidence,
    DataSource,
    IntakeRecord,
    MealLabel,
    MenuItem,
    Nutrients,
    Outcome,
    PatientProfile,
    Preference,
)
from medidiet.engine import RecommendationEngine
from medidiet.matcher import MatchRejectionCode
from medidiet.rules import load_baseline_rule_pack
from medidiet.safety import SafetyCode


NOW = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)


def profile(pack, **overrides):
    data = dict(
        patient_id="internal-p-1",
        age=54,
        height_cm=168,
        weight_kg=78,
        conditions={
            pack.concepts.require(CodeKind.CONDITION, "hypertension"),
            pack.concepts.require(CodeKind.CONDITION, "diabetes"),
        },
        allergens=set(),
        contraindications=set(),
        preferences=Preference(
            taste_tags={ConceptCode(CodeKind.TASTE_TAG, "light")},
            max_price_cents=3500,
            max_distance_meters=1500,
        ),
        key_risk_fields_confirmed=True,
        source=DataSource.PATIENT_REPORTED,
    )
    data.update(overrides)
    return PatientProfile(**data)


def intake(**overrides):
    data = dict(
        food_label="salty lunch",
        occurred_at=NOW,
        meal_label=MealLabel.LUNCH,
        portion="one bowl",
        nutrients=Nutrients(sodium_mg=600, sugar_g=5),
        confidence=Confidence(0.9),
        source=DataSource.SYSTEM_ESTIMATED,
    )
    data.update(overrides)
    return IntakeRecord(**data)


def menu(pack, item_id, **overrides):
    data = dict(
        item_id=item_id,
        merchant_id="shop",
        name=item_id,
        ingredients={ConceptCode(CodeKind.INGREDIENT, "fish"), ConceptCode(CodeKind.INGREDIENT, "vegetable")},
        allergens=set(),
        taste_tags={ConceptCode(CodeKind.TASTE_TAG, "light")},
        nutrition_tags={
            pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"),
            pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"),
            pack.concepts.require(CodeKind.NUTRITION_TAG, "vegetable_rich"),
        },
        contraindication_tags=set(),
        nutrients=Nutrients(energy_kcal=520, carbs_g=42, protein_g=30, fat_g=14, sodium_mg=450, sugar_g=6, fiber_g=5),
        nutrition_confidence=Confidence(0.9),
        source=DataSource.MERCHANT_LABEL,
        price_cents=3200,
        distance_meters=800,
        merchant_reliability=0.9,
    )
    data.update(overrides)
    return MenuItem(**data)


class RecommendationEngineTest(unittest.TestCase):
    def setUp(self):
        self.pack = load_baseline_rule_pack()
        self.engine = RecommendationEngine(self.pack, now=NOW)

    def test_recommends_safe_ranked_item_and_records_trace(self):
        candidates = [
            menu(self.pack, "ok", nutrition_tags={self.pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium")}),
            menu(self.pack, "best"),
        ]

        result = self.engine.recommend(profile(self.pack), [intake()], candidates, MealLabel.DINNER)

        self.assertEqual(result.outcome, Outcome.RECOMMENDED)
        self.assertEqual(result.recommended_items[0].item_id, "best")
        self.assertIn("低钠", result.patient_explanation)
        self.assertIn("主食", result.patient_explanation)
        self.assertEqual(result.trace.rule_version, "baseline-2026-05-15")
        self.assertEqual(result.trace.outcome, Outcome.RECOMMENDED)
        self.assertIn("best", result.trace.scores)
        payload = json.loads(result.trace.to_json())
        self.assertEqual(payload["outcome"], "recommended")

    def test_refuses_when_matcher_excludes_all_candidates(self):
        closed_item = menu(self.pack, "closed", available=False)

        result = self.engine.recommend(profile(self.pack), [], [closed_item], MealLabel.DINNER)

        self.assertEqual(result.outcome, Outcome.REFUSED)
        self.assertEqual(result.recommended_items, ())
        self.assertIn("暂不建议自动推荐", result.patient_explanation)
        self.assertEqual(result.trace.exclusions["closed"].code, MatchRejectionCode.UNAVAILABLE)
        payload = json.loads(result.trace.to_json())
        self.assertEqual(payload["exclusions"]["closed"]["code"], MatchRejectionCode.UNAVAILABLE.value)

    def test_routes_safety_events_to_human_review(self):
        peanut = ConceptCode(CodeKind.ALLERGEN, "peanut")
        allergic_patient = profile(self.pack, allergens={peanut})
        peanut_item = menu(self.pack, "peanut-fish", allergens={peanut})

        result = self.engine.recommend(allergic_patient, [], [peanut_item], MealLabel.DINNER)

        self.assertEqual(result.outcome, Outcome.HUMAN_REVIEW_REQUIRED)
        self.assertEqual(result.recommended_items, ())
        self.assertIn("营养师确认", result.patient_explanation)
        self.assertEqual(result.trace.safety_events[0].code, SafetyCode.ALLERGY_MATCH)
        payload = json.loads(result.trace.to_json())
        self.assertEqual(payload["safetyEvents"][0]["code"], SafetyCode.ALLERGY_MATCH.value)

    def test_rejects_string_meal_label(self):
        with self.assertRaises(TypeError):
            self.engine.recommend(profile(self.pack), [], [], "dinner")

    def test_fixture_demo_returns_trace_json(self):
        from medidiet.fixtures import demo_request

        patient, intake_records, menu_items, meal_label = demo_request()
        result = RecommendationEngine(load_baseline_rule_pack(), now=NOW).recommend(
            patient,
            intake_records,
            menu_items,
            meal_label,
        )

        trace_json = result.trace.to_json()
        self.assertTrue(trace_json.startswith("{"))
        self.assertIn('"traceId"', trace_json)
        self.assertIn('"outcome"', trace_json)
        self.assertIn(result.outcome.value, trace_json)


if __name__ == "__main__":
    unittest.main()
