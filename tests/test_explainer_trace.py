from datetime import datetime, timezone
import json
import unittest

from medidiet.domain import CodeKind, ConceptCode, Outcome, RiskLevel
from medidiet.explainer import ExplanationBuilder
from medidiet.matcher import MatchRejection, MatchRejectionCode
from medidiet.planner import MealInstruction
from medidiet.rules import LimitScope, NutrientMetric, load_baseline_rule_pack
from medidiet.safety import SafetyCode, SafetyEvent, SafetySeverity
from medidiet.trace import RecommendationTrace


class ExplanationTraceTest(unittest.TestCase):
    def setUp(self):
        self.pack = load_baseline_rule_pack()
        self.builder = ExplanationBuilder(self.pack)

    def test_patient_explanation_is_deterministic_safe_chinese_text(self):
        explanation = self.builder.patient_explanation(
            outcome=Outcome.RECOMMENDED,
            tags=(
                self.pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"),
                self.pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"),
            ),
            instructions=(
                MealInstruction.AVOID_EXTRA_SAUCE,
                MealInstruction.CONTROL_ADDED_SUGAR,
            ),
        )

        self.assertIn("低钠", explanation)
        self.assertIn("主食", explanation)
        self.assertIn("少放酱汁", explanation)
        self.assertNotIn("调整药物", explanation)
        self.assertNotIn("诊断", explanation)
        self.assertNotIn("治疗", explanation)

    def test_clinician_explanation_uses_structured_integer_codes(self):
        peanut = ConceptCode(CodeKind.ALLERGEN, "peanut")
        safety_event = SafetyEvent(
            code=SafetyCode.ALLERGY_MATCH,
            severity=SafetySeverity.HARD_BLOCK,
            patient_id="internal-p-1",
            entity_id="m-1",
            concept=peanut,
        )
        exclusion = MatchRejection(
            code=MatchRejectionCode.AVOID_TAG,
            item_id="m-2",
            concept=self.pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium"),
        )

        explanation = self.builder.clinician_explanation(
            rule_version=self.pack.version,
            safety_events=(safety_event,),
            exclusions={"m-2": exclusion},
            scores={"m-3": 88.5},
            matched_tags=(self.pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"),),
        )

        self.assertEqual(explanation["ruleVersion"], "baseline-2026-05-15")
        self.assertEqual(explanation["safetyEvents"][0]["code"], SafetyCode.ALLERGY_MATCH.value)
        self.assertIsInstance(explanation["safetyEvents"][0]["code"], int)
        self.assertEqual(explanation["exclusions"]["m-2"]["code"], MatchRejectionCode.AVOID_TAG.value)
        self.assertEqual(explanation["scores"]["m-3"], 88.5)
        self.assertIn("llmBoundary", explanation)

    def test_trace_serializes_camel_case_context_with_integer_codes(self):
        created_at = datetime(2026, 5, 16, 9, 30, tzinfo=timezone.utc)
        safety_event = SafetyEvent(
            code=SafetyCode.NUTRIENT_LIMIT_EXCEEDED,
            severity=SafetySeverity.HARD_BLOCK,
            patient_id="internal-p-1",
            entity_id="salty",
            metric=NutrientMetric.SODIUM_MG,
            scope=LimitScope.PER_MEAL,
            measured_value=900,
            limit_value=700,
        )
        exclusion = MatchRejection(
            code=MatchRejectionCode.NUTRIENT_LIMIT_EXCEEDED,
            item_id="salty",
            metric=NutrientMetric.SODIUM_MG,
            scope=LimitScope.PER_MEAL,
            measured_value=900,
            limit_value=700,
        )
        trace = RecommendationTrace(
            trace_id="trace-1",
            patient_id="internal-p-1",
            rule_version="baseline-2026-05-15",
            outcome=Outcome.HUMAN_REVIEW_REQUIRED,
            risk_level=RiskLevel.HIGH,
            safety_events=(safety_event,),
            exclusions={"salty": exclusion},
            scores={"safe": 92.0},
            patient_explanation="需要营养师确认。",
            clinician_explanation={"ruleVersion": "baseline-2026-05-15"},
            created_at=created_at,
        )

        payload = json.loads(trace.to_json())

        self.assertEqual(payload["traceId"], "trace-1")
        self.assertEqual(payload["patientId"], "internal-p-1")
        self.assertEqual(payload["ruleVersion"], "baseline-2026-05-15")
        self.assertEqual(payload["outcome"], "human_review_required")
        self.assertEqual(payload["riskLevel"], "high")
        self.assertEqual(payload["createdAt"], "2026-05-16T09:30:00+00:00")
        self.assertEqual(payload["safetyEvents"][0]["code"], SafetyCode.NUTRIENT_LIMIT_EXCEEDED.value)
        self.assertEqual(payload["exclusions"]["salty"]["code"], MatchRejectionCode.NUTRIENT_LIMIT_EXCEEDED.value)

    def test_trace_does_not_accept_sensitive_patient_fields(self):
        base_payload = dict(
            trace_id="trace-privacy",
            patient_id="internal-p-1",
            rule_version="baseline-2026-05-15",
            outcome=Outcome.RECOMMENDED,
            risk_level=RiskLevel.LOW,
        )

        with self.assertRaises(TypeError):
            RecommendationTrace(**base_payload, patient_name="张三")
        with self.assertRaises(TypeError):
            RecommendationTrace(**base_payload, phone_number="13800000000")
        with self.assertRaises(TypeError):
            RecommendationTrace(**base_payload, photo_uri="file:///meal.jpg")


if __name__ == "__main__":
    unittest.main()
