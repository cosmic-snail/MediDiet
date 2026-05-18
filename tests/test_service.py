from datetime import datetime, timezone
import unittest

from medidiet.domain import CodeKind, DataSource, MealLabel


class ServiceConversionTest(unittest.TestCase):
    def test_patient_input_converts_to_domain_profile(self):
        from medidiet.service import (
            ConceptCodeInput,
            PatientProfileInput,
            PreferenceInput,
            patient_profile_from_input,
        )

        patient = patient_profile_from_input(
            "patient-001",
            PatientProfileInput(
                age=65,
                height_cm=170,
                weight_kg=72,
                conditions=(ConceptCodeInput(kind="condition", value="hypertension"),),
                allergens=(ConceptCodeInput(kind="allergen", value="peanut"),),
                contraindications=(ConceptCodeInput(kind="contraindication", value="high_sodium"),),
                preferences=PreferenceInput(
                    taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),),
                    disliked_ingredients=(),
                    max_price_cents=3000,
                    max_distance_meters=1000,
                ),
                key_risk_fields_confirmed=True,
            ),
        )

        self.assertEqual(patient.patient_id, "patient-001")
        self.assertEqual(next(iter(patient.conditions)).kind, CodeKind.CONDITION)
        self.assertEqual(next(iter(patient.allergens)).kind, CodeKind.ALLERGEN)
        self.assertEqual(next(iter(patient.preferences.taste_tags)).value, "light")
        self.assertEqual(patient.source, DataSource.PATIENT_REPORTED)

    def test_rejects_wrong_code_kind_for_patient_fields(self):
        from medidiet.service import ConceptCodeInput, PatientProfileInput, ServiceError, patient_profile_from_input

        with self.assertRaises(ServiceError) as ctx:
            patient_profile_from_input(
                "patient-001",
                PatientProfileInput(
                    age=65,
                    height_cm=170,
                    weight_kg=72,
                    conditions=(ConceptCodeInput(kind="allergen", value="peanut"),),
                    allergens=(),
                    contraindications=(),
                    key_risk_fields_confirmed=True,
                ),
            )

        self.assertEqual(ctx.exception.code, "INVALID_CODE_KIND")

    def test_simplified_menu_input_uses_safe_defaults(self):
        from medidiet.service import ConceptCodeInput, MenuItemInput, NutrientsInput, menu_item_from_input

        item = menu_item_from_input(
            MenuItemInput(
                item_id="steamed-fish-set",
                name="Steamed fish set",
                ingredients=(ConceptCodeInput(kind="ingredient", value="fish"),),
                allergens=(),
                taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),),
                nutrition_tags=(ConceptCodeInput(kind="nutrition_tag", value="low_sodium"),),
                contraindication_tags=(),
                nutrients=NutrientsInput(
                    energy_kcal=520,
                    carbs_g=58,
                    protein_g=34,
                    fat_g=14,
                    sodium_mg=520,
                    sugar_g=6,
                    fiber_g=7,
                ),
            )
        )

        self.assertEqual(item.item_id, "steamed-fish-set")
        self.assertEqual(item.merchant_id, "hospital-canteen")
        self.assertEqual(item.source, DataSource.HUMAN_CURATED)
        self.assertEqual(item.nutrition_confidence.value, 0.95)
        self.assertEqual(item.price_cents, 0)
        self.assertTrue(item.available)

    def test_intake_input_converts_to_domain_record(self):
        from medidiet.service import IntakeRecordInput, NutrientsInput, intake_record_from_input

        occurred_at = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        record = intake_record_from_input(
            IntakeRecordInput(
                food_label="Breakfast porridge",
                occurred_at=occurred_at,
                meal_label=MealLabel.BREAKFAST,
                portion="1 bowl",
                nutrients=NutrientsInput(energy_kcal=180, carbs_g=30, protein_g=6, fat_g=3),
                confidence=0.92,
                manually_corrected=False,
            )
        )

        self.assertEqual(record.food_label, "Breakfast porridge")
        self.assertEqual(record.meal_label, MealLabel.BREAKFAST)
        self.assertEqual(record.source, DataSource.PATIENT_REPORTED)
        self.assertEqual(record.confidence.value, 0.92)


class RecommendationApplicationServiceTest(unittest.TestCase):
    def patient_input(self):
        from medidiet.service import ConceptCodeInput, PatientProfileInput, PreferenceInput

        return PatientProfileInput(
            age=65,
            height_cm=170,
            weight_kg=72,
            conditions=(ConceptCodeInput(kind="condition", value="hypertension"),),
            allergens=(),
            contraindications=(),
            preferences=PreferenceInput(taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),)),
            key_risk_fields_confirmed=True,
        )

    def safe_menu(self):
        from medidiet.service import ConceptCodeInput, MenuItemInput, NutrientsInput

        return (
            MenuItemInput(
                item_id="steamed-fish-set",
                name="Steamed fish set",
                ingredients=(ConceptCodeInput(kind="ingredient", value="fish"),),
                taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),),
                nutrition_tags=(
                    ConceptCodeInput(kind="nutrition_tag", value="low_sodium"),
                    ConceptCodeInput(kind="nutrition_tag", value="controlled_carbs"),
                    ConceptCodeInput(kind="nutrition_tag", value="vegetable_rich"),
                ),
                nutrients=NutrientsInput(
                    energy_kcal=520,
                    carbs_g=58,
                    protein_g=34,
                    fat_g=14,
                    sodium_mg=520,
                    sugar_g=6,
                    fiber_g=7,
                ),
            ),
        )

    def test_recommends_after_patient_and_menu_are_configured(self):
        from medidiet.llm import MockLLMProvider
        from medidiet.service import RecommendationRequestInput, RecommendationService

        service = RecommendationService(
            llm_provider=MockLLMProvider(
                explanation_payload={
                    "patientExplanation": "LLM safe patient explanation.",
                    "clinicianExplanation": "LLM safe clinician explanation.",
                }
            )
        )
        service.upsert_patient("patient-001", self.patient_input())
        service.replace_today_menu(self.safe_menu())

        result = service.recommend(RecommendationRequestInput(patient_id="patient-001", meal_label=MealLabel.DINNER))

        self.assertEqual(result.outcome, "recommended")
        self.assertEqual(result.recommended_items[0]["itemId"], "steamed-fish-set")
        self.assertEqual(result.patient_explanation, "LLM safe patient explanation.")
        self.assertFalse(result.llm_used_fallback)
        self.assertIsNone(result.llm_fallback_reason)

    def test_returns_menu_not_configured_before_menu_upload(self):
        from medidiet.service import RecommendationRequestInput, RecommendationService, ServiceError

        service = RecommendationService()
        service.upsert_patient("patient-001", self.patient_input())

        with self.assertRaises(ServiceError) as ctx:
            service.recommend(RecommendationRequestInput(patient_id="patient-001", meal_label=MealLabel.DINNER))

        self.assertEqual(ctx.exception.code, "MENU_NOT_CONFIGURED")

    def test_temporary_taste_tags_do_not_mutate_patient_preferences(self):
        from medidiet.service import ConceptCodeInput, RecommendationRequestInput, RecommendationService

        service = RecommendationService()
        service.upsert_patient("patient-001", self.patient_input())
        service.replace_today_menu(self.safe_menu())

        service.recommend(
            RecommendationRequestInput(
                patient_id="patient-001",
                meal_label=MealLabel.DINNER,
                temporary_taste_tags=(ConceptCodeInput(kind="taste_tag", value="mild"),),
            )
        )

        stored_patient = service.store.patients["patient-001"]
        self.assertEqual({code.value for code in stored_patient.preferences.taste_tags}, {"light"})

    def test_records_reviews_but_does_not_change_outcome(self):
        from medidiet.service import NutritionistReviewInput, RecommendationRequestInput, RecommendationService

        service = RecommendationService()
        service.upsert_patient("patient-001", self.patient_input())
        service.replace_today_menu(self.safe_menu())
        service.record_nutritionist_review(
            NutritionistReviewInput(
                patient_id="patient-001",
                reviewer_id="nutritionist-1",
                note="请人工复核晚餐。",
                created_at=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
            )
        )

        result = service.recommend(RecommendationRequestInput(patient_id="patient-001", meal_label=MealLabel.DINNER))

        self.assertEqual(result.outcome, "recommended")
        self.assertEqual(result.nutritionist_reviews[0]["note"], "请人工复核晚餐。")


if __name__ == "__main__":
    unittest.main()
