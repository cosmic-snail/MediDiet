import os
import unittest

from fastapi.testclient import TestClient

from medidiet.server import create_app
from medidiet.service import RecommendationService


def _smoke_enabled() -> bool:
    required = (
        "MEDIDIET_LLM_SMOKE_TEST",
        "MEDIDIET_LLM_PROVIDER",
        "MEDIDIET_LLM_BASE_URL",
        "MEDIDIET_LLM_API_KEY",
        "MEDIDIET_LLM_MODEL",
    )
    return os.getenv("MEDIDIET_LLM_SMOKE_TEST") == "1" and all(os.getenv(name) for name in required)


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


@unittest.skipUnless(
    _smoke_enabled(),
    "HTTP LLM smoke test requires MEDIDIET_LLM_SMOKE_TEST=1 and complete LLM env vars",
)
class HTTPLLMSmokeTest(unittest.TestCase):
    def test_http_recommendation_returns_real_llm_explanation(self):
        client = TestClient(create_app(RecommendationService()))
        self.assertEqual(client.put("/patients/patient-001", json=patient_payload()).status_code, 200)
        self.assertEqual(client.put("/menus/today", json=menu_payload()).status_code, 200)

        response = client.post(
            "/recommendations",
            json={
                "patientId": "patient-001",
                "mealLabel": 3,
                "temporaryTasteTags": [{"kind": "taste_tag", "value": "light"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["outcome"], "recommended")
        self.assertFalse(
            body["explanation"]["llm"]["usedFallback"],
            f"LLM fallback reason: {body['explanation']['llm']['fallbackReason']}",
        )
        self.assertIsNone(body["explanation"]["llm"]["fallbackReason"])
        self.assertGreater(len(body["explanation"]["patient"].strip()), 0)
        self.assertEqual(body["recommendedItems"][0]["itemId"], "steamed-fish-set")


if __name__ == "__main__":
    unittest.main()
