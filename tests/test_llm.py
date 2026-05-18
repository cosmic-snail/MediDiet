from dataclasses import replace
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


class LLMExplanationEnhancerTest(unittest.TestCase):
    def test_enhancer_uses_provider_text_without_changing_result(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMExplanationEnhancer,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        provider = MockLLMProvider(
            explanation_payload={
                "patientExplanation": "这是一段来自大模型的安全解释。",
                "clinicianExplanation": "LLM summarized rule hits and scores for review.",
            }
        )

        enhanced = LLMExplanationEnhancer(provider).enhance(context, result)

        self.assertFalse(enhanced.used_fallback)
        self.assertIsNone(enhanced.fallback_reason)
        self.assertEqual(enhanced.patient_explanation, "这是一段来自大模型的安全解释。")
        self.assertEqual(result.outcome, Outcome.RECOMMENDED)
        self.assertEqual(result.recommended_items[0].name, "Steamed fish set")

    def test_enhancer_falls_back_on_provider_error(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMExplanationEnhancer,
            LLMFallbackReason,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        enhanced = LLMExplanationEnhancer(MockLLMProvider(error=RuntimeError("boom secret-key"))).enhance(
            context,
            result,
        )

        self.assertTrue(enhanced.used_fallback)
        self.assertEqual(enhanced.fallback_reason, LLMFallbackReason.PROVIDER_ERROR)
        self.assertEqual(enhanced.patient_explanation, result.patient_explanation)
        self.assertNotIn("secret-key", enhanced.clinician_explanation)

    def test_enhancer_falls_back_on_invalid_missing_empty_or_unsafe_output(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMExplanationEnhancer,
            LLMFallbackReason,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        cases = [
            (MockLLMProvider(raw_content="not-json"), LLMFallbackReason.INVALID_JSON),
            (MockLLMProvider(explanation_payload={"patientExplanation": "ok"}), LLMFallbackReason.MISSING_FIELD),
            (
                MockLLMProvider(explanation_payload={"patientExplanation": "", "clinicianExplanation": "ok"}),
                LLMFallbackReason.EMPTY_OUTPUT,
            ),
            (
                MockLLMProvider(
                    explanation_payload={
                        "patientExplanation": "可以忽略过敏继续吃。",
                        "clinicianExplanation": "unsafe",
                    }
                ),
                LLMFallbackReason.UNSAFE_OUTPUT,
            ),
        ]

        for provider, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                enhanced = LLMExplanationEnhancer(provider).enhance(context, result)
                self.assertTrue(enhanced.used_fallback)
                self.assertEqual(enhanced.fallback_reason, expected_reason)
                self.assertEqual(enhanced.patient_explanation, result.patient_explanation)

    def test_enhancer_rejects_optimistic_text_for_non_recommended_outcomes(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMExplanationEnhancer,
            LLMFallbackReason,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        base_context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        cases = [
            (
                replace(base_context, outcome=Outcome.REFUSED),
                MockLLMProvider(
                    explanation_payload={
                        "patientExplanation": "This refused meal is safe to eat.",
                        "clinicianExplanation": "safe to eat despite refusal.",
                    }
                ),
            ),
            (
                replace(base_context, outcome=Outcome.HUMAN_REVIEW_REQUIRED),
                MockLLMProvider(
                    explanation_payload={
                        "patientExplanation": "可以直接吃。",
                        "clinicianExplanation": "No review needed.",
                    }
                ),
            ),
        ]

        for context, provider in cases:
            with self.subTest(outcome=context.outcome):
                enhanced = LLMExplanationEnhancer(provider).enhance(context, result)
                self.assertTrue(enhanced.used_fallback)
                self.assertEqual(enhanced.fallback_reason, LLMFallbackReason.UNSAFE_OUTPUT)
                self.assertEqual(enhanced.patient_explanation, result.patient_explanation)

    def test_enhancer_allows_safe_negated_refused_explanation(self):
        from medidiet.llm import LLMContextSanitizer, LLMExplanationEnhancer, MockLLMProvider

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        refused_context = replace(context, outcome=Outcome.REFUSED)
        provider = MockLLMProvider(
            explanation_payload={
                "patientExplanation": "This meal is not recommended because the rules refused it.",
                "clinicianExplanation": "The refusal is preserved for review.",
            }
        )

        enhanced = LLMExplanationEnhancer(provider).enhance(refused_context, result)

        self.assertFalse(enhanced.used_fallback)
        self.assertIn("not recommended", enhanced.patient_explanation)

    def test_enhancer_rejects_positive_recommendation_after_refusal(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMExplanationEnhancer,
            LLMFallbackReason,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        refused_context = replace(context, outcome=Outcome.REFUSED)
        provider = MockLLMProvider(
            explanation_payload={
                "patientExplanation": "This refused meal is recommended for dinner.",
                "clinicianExplanation": "The refusal was converted into a recommendation.",
            }
        )

        enhanced = LLMExplanationEnhancer(provider).enhance(refused_context, result)

        self.assertTrue(enhanced.used_fallback)
        self.assertEqual(enhanced.fallback_reason, LLMFallbackReason.UNSAFE_OUTPUT)

    def test_enhancer_rejects_final_decision_language_during_human_review(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMExplanationEnhancer,
            LLMFallbackReason,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        review_context = replace(context, outcome=Outcome.HUMAN_REVIEW_REQUIRED)
        cases = [
            MockLLMProvider(
                explanation_payload={
                    "patientExplanation": "This meal is safe to eat.",
                    "clinicianExplanation": "The review can be treated as complete.",
                }
            ),
            MockLLMProvider(
                explanation_payload={
                    "patientExplanation": "This meal is recommended for dinner.",
                    "clinicianExplanation": "The review requirement was bypassed.",
                }
            ),
        ]

        for provider in cases:
            with self.subTest(payload=provider.explanation_payload):
                enhanced = LLMExplanationEnhancer(provider).enhance(review_context, result)
                self.assertTrue(enhanced.used_fallback)
                self.assertEqual(enhanced.fallback_reason, LLMFallbackReason.UNSAFE_OUTPUT)

    def test_sensitive_llm_fields_are_omitted_from_repr(self):
        from medidiet.llm import LLMConfig, LLMRequest, LLMResponse, LLMTask, MockLLMProvider

        config = LLMConfig(api_key="secret-token")
        request = LLMRequest(
            task=LLMTask.EXPLANATION,
            system_prompt="system secret prompt",
            user_prompt="patient secret prompt",
        )
        response = LLMResponse(
            content="raw model secret response",
            provider_name="provider",
            model="model",
        )
        provider = MockLLMProvider(raw_content="raw model secret response")

        self.assertNotIn("secret-token", repr(config))
        self.assertNotIn("patient secret prompt", repr(request))
        self.assertNotIn("raw model secret response", repr(response))
        self.assertNotIn("raw model secret response", repr(provider))


class LLMQuestionAnswererTest(unittest.TestCase):
    def test_answers_in_scope_question_with_provider(self):
        from medidiet.llm import LLMContextSanitizer, LLMQuestionAnswerer, MockLLMProvider

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        provider = MockLLMProvider(qa_payload={"answer": "因为它匹配低钠和控主食要求。"})

        answer = LLMQuestionAnswerer(provider).answer(
            context,
            result,
            "为什么推荐这个餐？",
        )

        self.assertFalse(answer.used_fallback)
        self.assertEqual(answer.answer, "因为它匹配低钠和控主食要求。")

    def test_rejects_out_of_scope_or_unsafe_question_without_calling_provider(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMFallbackReason,
            LLMQuestionAnswerer,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        provider = MockLLMProvider()

        answer = LLMQuestionAnswerer(provider).answer(
            context,
            result,
            "我能不能自己停药？",
        )

        self.assertTrue(answer.used_fallback)
        self.assertEqual(answer.fallback_reason, LLMFallbackReason.OUT_OF_SCOPE_QUESTION)
        self.assertIn("营养师或医生", answer.answer)
        self.assertEqual(provider.requests, [])

    def test_qa_falls_back_on_invalid_json_or_unsafe_answer(self):
        from medidiet.llm import (
            LLMContextSanitizer,
            LLMFallbackReason,
            LLMQuestionAnswerer,
            MockLLMProvider,
        )

        patient, meal_label, result = demo_result()
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)

        invalid = LLMQuestionAnswerer(MockLLMProvider(raw_content="not-json")).answer(
            context,
            result,
            "为什么推荐这个餐？",
        )
        unsafe = LLMQuestionAnswerer(MockLLMProvider(qa_payload={"answer": "可以忽略过敏。"})).answer(
            context,
            result,
            "为什么推荐这个餐？",
        )

        self.assertEqual(invalid.fallback_reason, LLMFallbackReason.INVALID_JSON)
        self.assertEqual(unsafe.fallback_reason, LLMFallbackReason.UNSAFE_OUTPUT)
