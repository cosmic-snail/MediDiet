from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    Confidence,
    DataSource,
    IntakeRecord,
    MealLabel,
    MenuItem,
    Nutrients,
    PatientProfile,
    Preference,
)
from medidiet.rules import LimitScope, NutrientMetric, load_baseline_rule_pack
from medidiet.safety import SafetyCode, SafetyGate, SafetySeverity


NOW = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def patient(pack, **overrides):
    data = dict(
        patient_id="p-1",
        age=55,
        height_cm=170,
        weight_kg=82,
        conditions={pack.concepts.require(CodeKind.CONDITION, "hypertension")},
        allergens={ConceptCode(CodeKind.ALLERGEN, "peanut")},
        contraindications=set(),
        preferences=Preference(),
        key_risk_fields_confirmed=True,
        source=DataSource.PATIENT_REPORTED,
    )
    data.update(overrides)
    return PatientProfile(**data)


def menu_item(pack, **overrides):
    data = dict(
        item_id="m-1",
        merchant_id="shop-1",
        name="Chicken bowl",
        ingredients={ConceptCode(CodeKind.INGREDIENT, "chicken")},
        allergens=set(),
        taste_tags={ConceptCode(CodeKind.TASTE_TAG, "balanced")},
        nutrients=Nutrients(energy_kcal=500, carbs_g=45, protein_g=30, fat_g=18, sodium_mg=500, sugar_g=5, fiber_g=4),
        nutrition_confidence=Confidence(0.9),
        source=DataSource.MERCHANT_LABEL,
        price_cents=3000,
        distance_meters=800,
        merchant_reliability=0.9,
    )
    data.update(overrides)
    return MenuItem(**data)


class SafetyGateTest(unittest.TestCase):
    def setUp(self):
        self.pack = load_baseline_rule_pack()
        self.log_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.log_dir.name) / "safety.log"
        self.gate = SafetyGate(self.pack, log_file_path=self.log_path)

    def tearDown(self):
        self.log_dir.cleanup()

    def test_safety_events_use_integer_enum_codes_not_strings(self):
        result = self.gate.evaluate(patient(self.pack, age=12), [])

        self.assertEqual(result.hard_blocks[0].code, SafetyCode.OUT_OF_SCOPE_NON_ADULT)
        self.assertIsInstance(result.hard_blocks[0].code, SafetyCode)
        self.assertIsInstance(result.hard_blocks[0].code.value, int)
        self.assertNotIsInstance(result.hard_blocks[0], str)
        self.assertNotIsInstance(result.hard_blocks[0].code.value, float)

    def test_allergy_match_is_hard_block_and_warning_log(self):
        peanut = ConceptCode(CodeKind.ALLERGEN, "peanut")
        item = menu_item(self.pack, name="Peanut chicken", allergens={peanut})

        result = self.gate.evaluate(patient(self.pack), [item])

        event = result.hard_blocks[0]
        self.assertEqual(event.code, SafetyCode.ALLERGY_MATCH)
        self.assertEqual(event.severity, SafetySeverity.HARD_BLOCK)
        self.assertEqual(event.entity_id, "m-1")
        self.assertEqual(event.concept, peanut)
        self.assert_warning_logged(SafetyCode.ALLERGY_MATCH)

    def test_unconfirmed_profile_requires_review_and_warning_log(self):
        result = self.gate.evaluate(patient(self.pack, key_risk_fields_confirmed=False), [])

        event = result.uncertainties[0]
        self.assertEqual(event.code, SafetyCode.PATIENT_PROFILE_UNCONFIRMED)
        self.assertEqual(event.severity, SafetySeverity.UNCERTAINTY)
        self.assert_warning_logged(SafetyCode.PATIENT_PROFILE_UNCONFIRMED)

    def test_low_confidence_intake_requires_review_and_warning_log(self):
        intake = IntakeRecord(
            food_label="unknown bowl",
            occurred_at=NOW,
            meal_label=MealLabel.LUNCH,
            portion="one bowl",
            nutrients=Nutrients(sodium_mg=600),
            confidence=Confidence(0.4),
            source=DataSource.SYSTEM_ESTIMATED,
        )

        result = self.gate.evaluate(patient(self.pack), [], [intake])

        event = result.uncertainties[0]
        self.assertEqual(event.code, SafetyCode.LOW_CONFIDENCE_INTAKE)
        self.assertEqual(event.entity_id, "unknown bowl")
        self.assert_warning_logged(SafetyCode.LOW_CONFIDENCE_INTAKE)

    def test_menu_per_meal_nutrient_limit_is_hard_block_and_warning_log(self):
        salty_item = menu_item(self.pack, item_id="salty", nutrients=Nutrients(sodium_mg=900))

        result = self.gate.evaluate(patient(self.pack), [salty_item])

        event = result.hard_blocks[0]
        self.assertEqual(event.code, SafetyCode.NUTRIENT_LIMIT_EXCEEDED)
        self.assertEqual(event.entity_id, "salty")
        self.assertEqual(event.metric, NutrientMetric.SODIUM_MG)
        self.assertEqual(event.scope, LimitScope.PER_MEAL)
        self.assertEqual(event.measured_value, 900)
        self.assertEqual(event.limit_value, 700)
        self.assert_warning_logged(SafetyCode.NUTRIENT_LIMIT_EXCEEDED)

    def test_safe_loop_does_not_emit_below_warning_logs(self):
        safe_items = [
            menu_item(self.pack, item_id=f"safe-{index}", nutrients=Nutrients(sodium_mg=450))
            for index in range(20)
        ]

        result = self.gate.evaluate(patient(self.pack, allergens=set()), safe_items)

        self.assertFalse(result.requires_human_review)
        self.assertEqual(self.log_path.read_text(), "")

    def assert_warning_logged(self, code):
        log_text = self.log_path.read_text()
        self.assertIn("WARNING", log_text)
        self.assertIn(f"code={code.value}", log_text)
        self.assertIn(f"code_name={code.name}", log_text)
        self.assertIn("pid=", log_text)
        self.assertIn("tid=", log_text)
        self.assertRegex(log_text, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


if __name__ == "__main__":
    unittest.main()
