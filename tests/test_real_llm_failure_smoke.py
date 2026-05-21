"""Opt-in smoke test for LLM provider failure fallback behavior."""

from __future__ import annotations

import os

import pytest

from medidiet.engine import RecommendationEngine
from medidiet.fixtures import DEMO_NOW, demo_request
from medidiet.llm import (
    LLMConfig,
    LLMContextSanitizer,
    LLMExplanationEnhancer,
    LLMFallbackReason,
    OpenAICompatibleLLMProvider,
)
from medidiet.rules import load_baseline_rule_pack


@pytest.mark.skipif(
    os.getenv("MEDIDIET_LLM_SMOKE_TEST") != "1",
    reason="requires MEDIDIET_LLM_SMOKE_TEST=1",
)
def test_real_llm_provider_error_uses_fallback_without_changing_result():
    patient, intake_records, menu_items, meal_label = demo_request()
    result = RecommendationEngine(load_baseline_rule_pack(), now=DEMO_NOW).recommend(
        patient,
        intake_records,
        menu_items,
        meal_label,
    )
    context = LLMContextSanitizer().sanitize(result, patient, meal_label)
    bad_config = LLMConfig(
        provider="openai_compatible",
        base_url="https://127.0.0.1:9",
        api_key="test-key",
        model="test-model",
        timeout_seconds=1,
    )
    provider = OpenAICompatibleLLMProvider(bad_config)

    enhanced = LLMExplanationEnhancer(provider).enhance(context, result)

    assert enhanced.used_fallback is True
    assert enhanced.fallback_reason is LLMFallbackReason.PROVIDER_ERROR
    assert enhanced.patient_explanation == result.patient_explanation
    assert result.outcome == result.trace.outcome
    assert result.recommended_items
