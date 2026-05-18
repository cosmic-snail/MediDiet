import os
import unittest

from medidiet.engine import RecommendationEngine
from medidiet.fixtures import DEMO_NOW, demo_request
from medidiet.llm import (
    LLMConfig,
    LLMContextSanitizer,
    LLMExplanationEnhancer,
    OpenAICompatibleLLMProvider,
)
from medidiet.rules import load_baseline_rule_pack


def _smoke_enabled() -> bool:
    required = (
        "MEDIDIET_LLM_SMOKE_TEST",
        "MEDIDIET_LLM_PROVIDER",
        "MEDIDIET_LLM_BASE_URL",
        "MEDIDIET_LLM_API_KEY",
        "MEDIDIET_LLM_MODEL",
    )
    return os.getenv("MEDIDIET_LLM_SMOKE_TEST") == "1" and all(os.getenv(name) for name in required)


@unittest.skipUnless(
    _smoke_enabled(),
    "DeepSeek/OpenAI-compatible smoke test requires MEDIDIET_LLM_SMOKE_TEST=1 and LLM env vars",
)
class DeepSeekSmokeTest(unittest.TestCase):
    def test_real_provider_returns_non_empty_explanation(self):
        patient, intake_records, menu_items, meal_label = demo_request()
        result = RecommendationEngine(load_baseline_rule_pack(), now=DEMO_NOW).recommend(
            patient,
            intake_records,
            menu_items,
            meal_label,
        )
        config = LLMConfig.from_env()
        provider = OpenAICompatibleLLMProvider(config)
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)

        self.assertNotIn(patient.patient_id, str(context.to_dict()))

        enhanced = LLMExplanationEnhancer(provider).enhance(context, result)

        self.assertFalse(
            enhanced.used_fallback,
            f"LLM smoke test fell back with reason {enhanced.fallback_reason}",
        )
        self.assertIsNone(enhanced.fallback_reason)
        self.assertGreater(len(enhanced.patient_explanation.strip()), 0)
        self.assertGreater(len(enhanced.clinician_explanation.strip()), 0)


if __name__ == "__main__":
    unittest.main()
