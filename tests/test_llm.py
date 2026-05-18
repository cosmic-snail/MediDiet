from enum import IntEnum
import unittest

from medidiet.domain import CodeKind, MealLabel, Outcome, RiskLevel
from medidiet.engine import RecommendationEngine
from medidiet.fixtures import DEMO_NOW, demo_request
from medidiet.rules import load_baseline_rule_pack


def demo_result():
    patient, intake_records, menu_items, meal_label = demo_request()
    result = RecommendationEngine(load_baseline_rule_pack(), now=DEMO_NOW).recommend(
        patient,
        intake_records,
        menu_items,
        meal_label,
    )
    return patient, meal_label, result


class LLMContractTest(unittest.TestCase):
    def test_fallback_reason_is_integer_enum(self):
        from medidiet.llm import LLMFallbackReason

        self.assertTrue(issubclass(LLMFallbackReason, IntEnum))
        self.assertEqual(LLMFallbackReason.PROVIDER_NOT_CONFIGURED.value, 6001)
        self.assertEqual(LLMFallbackReason.OUT_OF_SCOPE_QUESTION.value, 6007)

    def test_sanitizer_excludes_patient_id_and_keeps_safe_context(self):
        from medidiet.llm import LLMContextSanitizer

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(
            result=result,
            patient=patient,
            meal_label=meal_label,
        )
        payload = context.to_dict()

        self.assertEqual(context.outcome, Outcome.RECOMMENDED)
        self.assertEqual(context.risk_level, RiskLevel.LOW)
        self.assertEqual(context.rule_version, "baseline-2026-05-15")
        self.assertEqual(context.meal_label, MealLabel.DINNER)
        self.assertEqual(context.selected_item_name, "Steamed fish set")
        self.assertIn(CodeKind.CONDITION.value, payload["conditions"][0])
        self.assertIn("ruleVersion", payload)
        self.assertIn("safetyEventCodes", payload)
        self.assertNotIn("patientId", payload)
        self.assertNotIn(patient.patient_id, str(payload))
