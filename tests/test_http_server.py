from datetime import datetime, timezone
import unittest

from fastapi.testclient import TestClient


def patient_payload():
    return {
        "age": 65,
        "heightCm": 170,
        "weightKg": 72,
        "conditions": [{"kind": "condition", "value": "hypertension"}],
        "allergens": [],
        "contraindications": [],
        "preferences": {
            "tasteTags": [{"kind": "taste_tag", "value": "light"}],
            "dislikedIngredients": [],
            "maxPriceCents": 3000,
            "maxDistanceMeters": 1000,
        },
        "keyRiskFieldsConfirmed": True,
    }


def menu_payload():
    return {
        "items": [
            {
                "itemId": "steamed-fish-set",
                "name": "Steamed fish set",
                "ingredients": [{"kind": "ingredient", "value": "fish"}],
                "allergens": [],
                "tasteTags": [{"kind": "taste_tag", "value": "light"}],
                "nutritionTags": [
                    {"kind": "nutrition_tag", "value": "low_sodium"},
                    {"kind": "nutrition_tag", "value": "controlled_carbs"},
                    {"kind": "nutrition_tag", "value": "vegetable_rich"},
                ],
                "contraindicationTags": [],
                "nutrients": {
                    "energyKcal": 520,
                    "carbsG": 58,
                    "proteinG": 34,
                    "fatG": 14,
                    "sodiumMg": 520,
                    "sugarG": 6,
                    "fiberG": 7,
                },
            }
        ]
    }


class HTTPServerTest(unittest.TestCase):
    def make_client(self):
        from medidiet.llm import MockLLMProvider
        from medidiet.server import create_app
        from medidiet.service import RecommendationService

        service = RecommendationService(
            llm_provider=MockLLMProvider(
                explanation_payload={
                    "patientExplanation": "LLM patient explanation.",
                    "clinicianExplanation": "LLM clinician explanation.",
                }
            )
        )
        return TestClient(create_app(service))

    def test_health_returns_versions(self):
        client = self.make_client()

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["version"], "0.1.1")
        self.assertEqual(body["ruleVersion"], "baseline-2026-05-15")

    def test_recommendation_flow_returns_llm_explanation(self):
        client = self.make_client()
        self.assertEqual(client.put("/patients/patient-001", json=patient_payload()).status_code, 200)
        self.assertEqual(client.put("/menus/today", json=menu_payload()).status_code, 200)
        review_response = client.post(
            "/reviews/nutritionist",
            json={
                "patientId": "patient-001",
                "reviewerId": "nutritionist-1",
                "note": "请人工复核。",
                "createdAt": "2026-05-18T09:00:00+00:00",
            },
        )
        self.assertEqual(review_response.status_code, 200)

        response = client.post(
            "/recommendations",
            json={
                "patientId": "patient-001",
                "mealLabel": 3,
                "temporaryTasteTags": [{"kind": "taste_tag", "value": "light"}],
                "debug": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["outcome"], "recommended")
        self.assertEqual(body["recommendedItems"][0]["itemId"], "steamed-fish-set")
        self.assertEqual(body["explanation"]["patient"], "LLM patient explanation.")
        self.assertFalse(body["explanation"]["llm"]["usedFallback"])
        self.assertEqual(body["nutritionistReviews"][0]["note"], "请人工复核。")
        self.assertIn("traceId", body)
        self.assertIn("trace", body)

    def test_missing_patient_uses_uniform_error_response(self):
        client = self.make_client()

        response = client.post("/recommendations", json={"patientId": "missing", "mealLabel": 3})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "PATIENT_NOT_FOUND")

    def test_invalid_code_kind_returns_422(self):
        client = self.make_client()
        payload = patient_payload()
        payload["conditions"] = [{"kind": "allergen", "value": "peanut"}]

        response = client.put("/patients/patient-001", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_CODE_KIND")

    def test_intake_endpoint_appends_record(self):
        client = self.make_client()
        client.put("/patients/patient-001", json=patient_payload())

        response = client.post(
            "/patients/patient-001/intake-records",
            json={
                "foodLabel": "Breakfast porridge",
                "occurredAt": "2026-05-18T08:00:00+00:00",
                "mealLabel": 1,
                "portion": "1 bowl",
                "nutrients": {"energyKcal": 180, "carbsG": 30, "proteinG": 6, "fatG": 3},
                "confidence": 0.92,
                "manuallyCorrected": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intakeRecordCount"], 1)

    def test_debug_state_returns_counts(self):
        client = self.make_client()
        client.put("/patients/patient-001", json=patient_payload())
        client.put("/menus/today", json=menu_payload())

        response = client.get("/debug/state")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["todayMenuCount"], 1)
        self.assertEqual(response.json()["patients"], ["patient-001"])

    def test_validation_errors_use_uniform_error_response(self):
        client = self.make_client()

        response = client.put("/menus/today", json={"items": [{"itemId": "bad", "name": "Missing nutrients"}]})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")


class HTTPServerFallbackTest(unittest.TestCase):
    def test_recommendation_succeeds_with_llm_provider_error(self):
        from medidiet.llm import MockLLMProvider
        from medidiet.server import create_app
        from medidiet.service import RecommendationService

        service = RecommendationService(llm_provider=MockLLMProvider(error=RuntimeError("provider down")))
        client = TestClient(create_app(service))
        client.put("/patients/patient-001", json=patient_payload())
        client.put("/menus/today", json=menu_payload())

        response = client.post("/recommendations", json={"patientId": "patient-001", "mealLabel": 3})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["outcome"], "recommended")
        self.assertTrue(body["explanation"]["llm"]["usedFallback"])
        self.assertEqual(body["explanation"]["llm"]["fallbackReason"], 6002)

    def test_missing_menu_returns_409(self):
        from medidiet.server import create_app
        from medidiet.service import RecommendationService

        client = TestClient(create_app(RecommendationService()))
        client.put("/patients/patient-001", json=patient_payload())

        response = client.post("/recommendations", json={"patientId": "patient-001", "mealLabel": 3})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MENU_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
