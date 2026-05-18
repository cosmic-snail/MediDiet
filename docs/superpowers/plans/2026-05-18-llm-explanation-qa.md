# LLM Explanation and QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional OpenAI-compatible LLM post-processing layer for patient explanation enhancement and recommendation-scoped QA without changing the rules-based recommendation result.

**Architecture:** Keep `RecommendationEngine` deterministic and rule-owned. Add `src/medidiet/llm.py` as an isolated post-processing module containing typed LLM contracts, context sanitization, mock provider, OpenAI-compatible provider, safety validation, explanation enhancement, and QA. Normal tests run offline; a DeepSeek-compatible smoke test is opt-in via environment variables.

**Tech Stack:** Python 3.11+ standard library, `dataclasses`, `enum.IntEnum`, `typing.Protocol`, `json`, `urllib.request`, `unittest`, environment variables.

---

## Existing Context

Current code has no real LLM integration:

- `src/medidiet/explainer.py` generates deterministic patient and clinician explanations.
- `src/medidiet/engine.py` returns `RecommendationResult`.
- `src/medidiet/trace.py` serializes `RecommendationTrace`.
- `src/medidiet/ports.py` defines external extension ports, but no LLM port.
- `docs/software-design.md` currently states patient explanations are rule templates and do not call an LLM.

The new LLM layer must be optional and must never change:

- `RecommendationResult.outcome`
- `RecommendationResult.recommended_items`
- `RecommendationTrace.safety_events`
- `RecommendationTrace.exclusions`
- `RecommendationTrace.scores`

Untracked files in the working tree may exist and must be left alone unless the user explicitly asks otherwise.

## File Structure

Create:

- `src/medidiet/llm.py` - LLM data contracts, config, sanitizer, providers, prompt construction, validators, explanation enhancer, QA.
- `tests/test_llm.py` - offline deterministic unit tests.
- `tests/test_llm_deepseek_smoke.py` - opt-in real DeepSeek/OpenAI-compatible integration smoke test, skipped by default.

Modify:

- `src/medidiet/__init__.py` - export stable public LLM types.
- `docs/api.md` - add LLM API section.
- `docs/software-design.md` - update architecture and current limitation.
- `docs/usage.md` - add DeepSeek/OpenAI-compatible configuration and smoke test usage.
- `docs/testing.md` - add LLM unit and smoke test coverage.

Do not modify recommendation selection logic unless a task explicitly says so.

---

### Task 1: LLM Contracts and Sanitized Context

**Files:**
- Create: `src/medidiet/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests for LLM contracts and sanitizer**

Create `tests/test_llm.py` with these initial tests:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.LLMContractTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.llm'`.

- [ ] **Step 3: Implement minimal LLM contracts and sanitizer**

Create `src/medidiet/llm.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Protocol

from medidiet.domain import ConceptCode, MealLabel, Nutrients, Outcome, PatientProfile, RiskLevel
from medidiet.engine import RecommendationResult


class LLMTask(str, Enum):
    EXPLANATION = "explanation"
    QUESTION_ANSWERING = "question_answering"


class LLMFallbackReason(IntEnum):
    PROVIDER_NOT_CONFIGURED = 6001
    PROVIDER_ERROR = 6002
    INVALID_JSON = 6003
    MISSING_FIELD = 6004
    EMPTY_OUTPUT = 6005
    UNSAFE_OUTPUT = 6006
    OUT_OF_SCOPE_QUESTION = 6007


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "mock"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: int = 10
    send_patient_id: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class LLMRequest:
    task: LLMTask
    system_prompt: str
    user_prompt: str
    response_format: str = "json"

    def __post_init__(self) -> None:
        if not isinstance(self.task, LLMTask):
            raise TypeError("task must be an LLMTask")


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider_name: str
    model: str


class LLMProviderPort(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


@dataclass(frozen=True)
class LLMRecommendationContext:
    outcome: Outcome
    risk_level: RiskLevel
    rule_version: str
    conditions: tuple[ConceptCode, ...]
    allergens: tuple[ConceptCode, ...]
    meal_label: MealLabel | None
    selected_item_name: str | None
    selected_item_nutrients: Nutrients | None
    safety_event_codes: tuple[int, ...]
    exclusion_codes: tuple[int, ...]
    matched_nutrition_tags: tuple[ConceptCode, ...]
    patient_explanation: str
    clinician_explanation: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "riskLevel": self.risk_level.value,
            "ruleVersion": self.rule_version,
            "conditions": [_concept_to_dict(code) for code in self.conditions],
            "allergens": [_concept_to_dict(code) for code in self.allergens],
            "mealLabel": self.meal_label.value if self.meal_label is not None else None,
            "selectedItemName": self.selected_item_name,
            "selectedItemNutrients": _nutrients_to_dict(self.selected_item_nutrients),
            "safetyEventCodes": list(self.safety_event_codes),
            "exclusionCodes": list(self.exclusion_codes),
            "matchedNutritionTags": [_concept_to_dict(code) for code in self.matched_nutrition_tags],
            "patientExplanation": self.patient_explanation,
            "clinicianExplanation": self.clinician_explanation,
        }


class LLMContextSanitizer:
    def sanitize(
        self,
        result: RecommendationResult,
        patient: PatientProfile,
        meal_label: MealLabel | None = None,
    ) -> LLMRecommendationContext:
        selected_item = result.recommended_items[0] if result.recommended_items else None
        matched_tags = result.trace.clinician_explanation.get("matchedTags", ())
        return LLMRecommendationContext(
            outcome=result.outcome,
            risk_level=result.trace.risk_level,
            rule_version=result.trace.rule_version,
            conditions=tuple(sorted(patient.conditions, key=lambda code: (code.kind.value, code.value))),
            allergens=tuple(sorted(patient.allergens, key=lambda code: (code.kind.value, code.value))),
            meal_label=meal_label,
            selected_item_name=selected_item.name if selected_item is not None else None,
            selected_item_nutrients=selected_item.nutrients if selected_item is not None else None,
            safety_event_codes=tuple(event.code.value for event in result.trace.safety_events),
            exclusion_codes=tuple(rejection.code.value for rejection in result.trace.exclusions.values()),
            matched_nutrition_tags=_matched_tags_from_payload(matched_tags),
            patient_explanation=result.patient_explanation,
            clinician_explanation=result.clinician_explanation,
        )


def _matched_tags_from_payload(payload: object) -> tuple[ConceptCode, ...]:
    if not isinstance(payload, list | tuple):
        return ()
    tags: list[ConceptCode] = []
    for item in payload:
        if isinstance(item, dict) and item.get("kind") == "nutrition_tag" and isinstance(item.get("value"), str):
            from medidiet.domain import CodeKind

            tags.append(ConceptCode(CodeKind.NUTRITION_TAG, item["value"]))
    return tuple(tags)


def _concept_to_dict(code: ConceptCode) -> dict[str, str]:
    return {"kind": code.kind.value, "value": code.value}


def _nutrients_to_dict(nutrients: Nutrients | None) -> dict[str, float] | None:
    if nutrients is None:
        return None
    return {
        "energyKcal": nutrients.energy_kcal,
        "carbsG": nutrients.carbs_g,
        "proteinG": nutrients.protein_g,
        "fatG": nutrients.fat_g,
        "sodiumMg": nutrients.sodium_mg,
        "sugarG": nutrients.sugar_g,
        "fiberG": nutrients.fiber_g,
    }
```

- [ ] **Step 4: Run tests and full suite**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.LLMContractTest -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/llm.py tests/test_llm.py
git commit -m "feat: add LLM contracts and sanitizer"
```

---

### Task 2: Explanation Enhancer, Mock Provider, and Fallbacks

**Files:**
- Modify: `src/medidiet/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Append failing explanation enhancer tests**

Append these tests to `tests/test_llm.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.LLMExplanationEnhancerTest -v
```

Expected: FAIL with `ImportError` for `LLMExplanationEnhancer` or `MockLLMProvider`.

- [ ] **Step 3: Implement mock provider, enhanced explanation, prompt, parser, and validators**

Update `src/medidiet/llm.py` by adding:

```python
import json
```

Add these dataclasses and classes after `LLMRecommendationContext`:

```python
@dataclass(frozen=True)
class LLMEnhancedExplanation:
    patient_explanation: str
    clinician_explanation: str
    used_fallback: bool
    fallback_reason: LLMFallbackReason | None


class MockLLMProvider:
    def __init__(
        self,
        explanation_payload: dict[str, object] | None = None,
        qa_payload: dict[str, object] | None = None,
        raw_content: str | None = None,
        error: Exception | None = None,
    ):
        self.explanation_payload = explanation_payload or {
            "patientExplanation": "这份推荐符合当前规则，请按建议控制酱汁和甜饮。",
            "clinicianExplanation": "Mock clinician explanation generated from sanitized context.",
        }
        self.qa_payload = qa_payload or {"answer": "这份回答基于当前推荐结果和规则命中。"}
        self.raw_content = raw_content
        self.error = error
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.raw_content is not None:
            content = self.raw_content
        elif request.task is LLMTask.EXPLANATION:
            content = json.dumps(self.explanation_payload, ensure_ascii=False)
        else:
            content = json.dumps(self.qa_payload, ensure_ascii=False)
        return LLMResponse(content=content, provider_name="mock", model="mock")


class LLMExplanationEnhancer:
    def __init__(self, provider: LLMProviderPort | None):
        self.provider = provider

    def enhance(self, context: LLMRecommendationContext, result: RecommendationResult) -> LLMEnhancedExplanation:
        if self.provider is None:
            return _fallback_explanation(result, LLMFallbackReason.PROVIDER_NOT_CONFIGURED)
        request = LLMRequest(
            task=LLMTask.EXPLANATION,
            system_prompt=_system_prompt(),
            user_prompt=_explanation_prompt(context),
        )
        try:
            response = self.provider.complete(request)
        except Exception:
            return _fallback_explanation(result, LLMFallbackReason.PROVIDER_ERROR)
        payload, reason = _parse_json_object(response.content)
        if reason is not None:
            return _fallback_explanation(result, reason)
        patient_text = payload.get("patientExplanation")
        clinician_text = payload.get("clinicianExplanation")
        reason = _validate_required_texts(
            {
                "patientExplanation": patient_text,
                "clinicianExplanation": clinician_text,
            },
            context,
        )
        if reason is not None:
            return _fallback_explanation(result, reason)
        return LLMEnhancedExplanation(
            patient_explanation=patient_text,
            clinician_explanation=clinician_text,
            used_fallback=False,
            fallback_reason=None,
        )


def _fallback_explanation(result: RecommendationResult, reason: LLMFallbackReason) -> LLMEnhancedExplanation:
    return LLMEnhancedExplanation(
        patient_explanation=result.patient_explanation,
        clinician_explanation="LLM enhancement unavailable; deterministic template explanation was used.",
        used_fallback=True,
        fallback_reason=reason,
    )


def _system_prompt() -> str:
    return (
        "You explain a completed rules-based nutrition recommendation. "
        "Do not change the recommendation outcome. Do not recommend excluded or unsafe items. "
        "Do not tell users to ignore allergies, contraindications, clinician review, or safety warnings. "
        "Do not provide diagnosis, medication adjustment, or treatment instructions. "
        "Use only the provided structured context. Return JSON only."
    )


def _explanation_prompt(context: LLMRecommendationContext) -> str:
    return json.dumps(
        {
            "task": "explain_recommendation",
            "context": context.to_dict(),
            "requiredOutput": {
                "patientExplanation": "short Chinese patient-facing explanation",
                "clinicianExplanation": "concise clinician-facing explanation",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _parse_json_object(content: str) -> tuple[dict[str, object], LLMFallbackReason | None]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {}, LLMFallbackReason.INVALID_JSON
    if not isinstance(payload, dict):
        return {}, LLMFallbackReason.INVALID_JSON
    return payload, None


def _validate_required_texts(
    values: dict[str, object],
    context: LLMRecommendationContext,
) -> LLMFallbackReason | None:
    for key, value in values.items():
        if key not in values:
            return LLMFallbackReason.MISSING_FIELD
        if not isinstance(value, str):
            return LLMFallbackReason.MISSING_FIELD
        if not value.strip():
            return LLMFallbackReason.EMPTY_OUTPUT
        if _contains_unsafe_text(value, context):
            return LLMFallbackReason.UNSAFE_OUTPUT
    return None


def _contains_unsafe_text(text: str, context: LLMRecommendationContext) -> bool:
    lowered = text.lower()
    unsafe_phrases = (
        "忽略过敏",
        "忽略禁忌",
        "无需营养师",
        "无需医生",
        "不用人工审核",
        "自行调整药",
        "停药",
        "ignore allergy",
        "ignore contraindication",
        "ignore clinician",
        "adjust medication",
    )
    if any(phrase in lowered for phrase in unsafe_phrases):
        return True
    if context.outcome is Outcome.REFUSED and ("推荐成功" in text or "可以放心吃" in text):
        return True
    if context.outcome.name == "HUMAN_REVIEW_REQUIRED" and ("无需" in text and "审核" in text):
        return True
    return False
```

- [ ] **Step 4: Run tests and full suite**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.LLMExplanationEnhancerTest -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/llm.py tests/test_llm.py
git commit -m "feat: enhance explanations with optional LLM"
```

---

### Task 3: Recommendation-Scoped Question Answering

**Files:**
- Modify: `src/medidiet/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Append failing QA tests**

Append these tests to `tests/test_llm.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.LLMQuestionAnswererTest -v
```

Expected: FAIL with `ImportError` for `LLMQuestionAnswerer`.

- [ ] **Step 3: Implement QA answerer and question scope guard**

Update `src/medidiet/llm.py` by adding:

```python
@dataclass(frozen=True)
class LLMAnswer:
    answer: str
    used_fallback: bool
    fallback_reason: LLMFallbackReason | None


class LLMQuestionAnswerer:
    def __init__(self, provider: LLMProviderPort | None):
        self.provider = provider

    def answer(
        self,
        context: LLMRecommendationContext,
        result: RecommendationResult,
        question: str,
    ) -> LLMAnswer:
        if _is_out_of_scope_question(question):
            return _fallback_answer(LLMFallbackReason.OUT_OF_SCOPE_QUESTION)
        if self.provider is None:
            return _fallback_answer(LLMFallbackReason.PROVIDER_NOT_CONFIGURED)
        request = LLMRequest(
            task=LLMTask.QUESTION_ANSWERING,
            system_prompt=_system_prompt(),
            user_prompt=_qa_prompt(context, question),
        )
        try:
            response = self.provider.complete(request)
        except Exception:
            return _fallback_answer(LLMFallbackReason.PROVIDER_ERROR)
        payload, reason = _parse_json_object(response.content)
        if reason is not None:
            return _fallback_answer(reason)
        answer = payload.get("answer")
        reason = _validate_required_texts({"answer": answer}, context)
        if reason is not None:
            return _fallback_answer(reason)
        return LLMAnswer(answer=answer, used_fallback=False, fallback_reason=None)


def _fallback_answer(reason: LLMFallbackReason) -> LLMAnswer:
    if reason is LLMFallbackReason.OUT_OF_SCOPE_QUESTION:
        text = "这个问题超出了本次餐食推荐解释范围，请咨询营养师或医生。"
    else:
        text = "暂时无法使用大模型回答，我只能基于当前推荐结果说明：请遵循页面中的安全提示和营养师建议。"
    return LLMAnswer(answer=text, used_fallback=True, fallback_reason=reason)


def _qa_prompt(context: LLMRecommendationContext, question: str) -> str:
    return json.dumps(
        {
            "task": "answer_recommendation_question",
            "question": question,
            "context": context.to_dict(),
            "requiredOutput": {"answer": "Chinese answer constrained to this recommendation"},
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _is_out_of_scope_question(question: str) -> bool:
    lowered = question.lower()
    unsafe_markers = (
        "停药",
        "换药",
        "吃药",
        "诊断",
        "治疗",
        "忽略过敏",
        "忽略禁忌",
        "不审核",
        "medication",
        "diagnosis",
        "treatment",
        "ignore allergy",
        "ignore contraindication",
    )
    return any(marker in lowered for marker in unsafe_markers)
```

- [ ] **Step 4: Run tests and full suite**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.LLMQuestionAnswererTest -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/llm.py tests/test_llm.py
git commit -m "feat: answer recommendation questions with LLM"
```

---

### Task 4: OpenAI-Compatible Provider and Environment Config

**Files:**
- Modify: `src/medidiet/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Append failing provider/config tests**

Append these tests to `tests/test_llm.py`:

```python
class OpenAICompatibleLLMProviderTest(unittest.TestCase):
    def test_config_loads_from_environment_without_enabling_patient_id(self):
        import os
        from unittest.mock import patch

        from medidiet.llm import LLMConfig

        env = {
            "MEDIDIET_LLM_PROVIDER": "openai_compatible",
            "MEDIDIET_LLM_BASE_URL": "https://api.deepseek.com",
            "MEDIDIET_LLM_API_KEY": "secret",
            "MEDIDIET_LLM_MODEL": "deepseek-v4",
            "MEDIDIET_LLM_TIMEOUT_SECONDS": "7",
        }
        with patch.dict(os.environ, env, clear=False):
            config = LLMConfig.from_env()

        self.assertEqual(config.provider, "openai_compatible")
        self.assertEqual(config.base_url, "https://api.deepseek.com")
        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.model, "deepseek-v4")
        self.assertEqual(config.timeout_seconds, 7)
        self.assertFalse(config.send_patient_id)

    def test_openai_provider_builds_request_and_does_not_leak_api_key(self):
        import json
        from unittest.mock import patch

        from medidiet.llm import (
            LLMConfig,
            LLMRequest,
            LLMTask,
            OpenAICompatibleLLMProvider,
        )

        captured = {}

        class FakeHTTPResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "{\"answer\": \"ok\"}"}}]},
                    ensure_ascii=False,
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.headers.get("Authorization")
            return FakeHTTPResponse()

        provider = OpenAICompatibleLLMProvider(
            LLMConfig(
                provider="openai_compatible",
                base_url="https://api.deepseek.com",
                api_key="secret-token",
                model="deepseek-v4",
                timeout_seconds=3,
            )
        )
        with patch("urllib.request.urlopen", fake_urlopen):
            response = provider.complete(
                LLMRequest(
                    task=LLMTask.QUESTION_ANSWERING,
                    system_prompt="system",
                    user_prompt="user",
                )
            )

        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(captured["body"]["model"], "deepseek-v4")
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(response.content, '{"answer": "ok"}')
        self.assertNotIn("secret-token", repr(response))

    def test_openai_provider_rejects_missing_required_config(self):
        from medidiet.llm import LLMConfig, OpenAICompatibleLLMProvider

        with self.assertRaises(ValueError):
            OpenAICompatibleLLMProvider(LLMConfig(provider="openai_compatible", api_key="secret"))
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.OpenAICompatibleLLMProviderTest -v
```

Expected: FAIL with missing `LLMConfig.from_env` or `OpenAICompatibleLLMProvider`.

- [ ] **Step 3: Implement env config and OpenAI-compatible provider**

Update imports in `src/medidiet/llm.py`:

```python
import os
import urllib.error
import urllib.request
```

Add `from_env` inside `LLMConfig`:

```python
    @classmethod
    def from_env(cls) -> "LLMConfig":
        timeout_raw = os.getenv("MEDIDIET_LLM_TIMEOUT_SECONDS", "10")
        try:
            timeout_seconds = int(timeout_raw)
        except ValueError as exc:
            raise ValueError("MEDIDIET_LLM_TIMEOUT_SECONDS must be an integer") from exc
        return cls(
            provider=os.getenv("MEDIDIET_LLM_PROVIDER", "mock"),
            base_url=os.getenv("MEDIDIET_LLM_BASE_URL"),
            api_key=os.getenv("MEDIDIET_LLM_API_KEY"),
            model=os.getenv("MEDIDIET_LLM_MODEL"),
            timeout_seconds=timeout_seconds,
            send_patient_id=False,
        )
```

Add provider class:

```python
class OpenAICompatibleLLMProvider:
    def __init__(self, config: LLMConfig):
        if config.provider != "openai_compatible":
            raise ValueError("config.provider must be openai_compatible")
        if not config.base_url or not config.api_key or not config.model:
            raise ValueError("base_url, api_key, and model are required")
        self.config = config

    def complete(self, request: LLMRequest) -> LLMResponse:
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        http_request = urllib.request.Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("LLM provider request failed") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM provider response missing message content") from exc
        if not isinstance(content, str):
            raise RuntimeError("LLM provider message content must be a string")
        return LLMResponse(
            content=content,
            provider_name="openai_compatible",
            model=self.config.model or "",
        )
```

- [ ] **Step 4: Run tests and full suite**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm.OpenAICompatibleLLMProviderTest -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/llm.py tests/test_llm.py
git commit -m "feat: add OpenAI-compatible LLM provider"
```

---

### Task 5: Opt-In DeepSeek Smoke Test

**Files:**
- Create: `tests/test_llm_deepseek_smoke.py`
- Modify: `docs/usage.md`
- Modify: `docs/testing.md`

- [ ] **Step 1: Write skipped-by-default smoke test**

Create `tests/test_llm_deepseek_smoke.py`:

```python
import os
import unittest

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
```

- [ ] **Step 2: Run smoke test without env and verify it skips**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm_deepseek_smoke -v
```

Expected: OK with 1 skipped test.

- [ ] **Step 3: Document smoke test in usage and testing docs**

Append this section to `docs/usage.md`:

```markdown

## 13. 可选 DeepSeek / OpenAI-compatible LLM 配置

MediDiet 的 LLM 层是可选增强层。推荐结果仍由规则引擎决定，大模型只能增强解释或回答本次推荐相关问题。

环境变量：

```bash
export MEDIDIET_LLM_PROVIDER=openai_compatible
export MEDIDIET_LLM_BASE_URL=https://api.deepseek.com
export MEDIDIET_LLM_API_KEY=你的_api_key
export MEDIDIET_LLM_MODEL=deepseek-v4
export MEDIDIET_LLM_TIMEOUT_SECONDS=10
```

可选真实接口 smoke test：

```bash
MEDIDIET_LLM_SMOKE_TEST=1 \
MEDIDIET_LLM_PROVIDER=openai_compatible \
MEDIDIET_LLM_BASE_URL=https://api.deepseek.com \
MEDIDIET_LLM_API_KEY=你的_api_key \
MEDIDIET_LLM_MODEL=deepseek-v4 \
PYTHONPATH=src python -m unittest tests.test_llm_deepseek_smoke -v
```

该测试默认跳过。启用后会访问真实模型 API，可能产生费用。测试不会发送患者真实 id、原始图片、地址或完整病历。
```

Append this section to `docs/testing.md`:

```markdown

## 12. LLM 测试策略

LLM 单元测试默认离线运行，使用 `MockLLMProvider` 覆盖解释增强、问答、fallback、安全输出校验和 provider 请求构造。

真实 DeepSeek/OpenAI-compatible smoke test 位于 `tests/test_llm_deepseek_smoke.py`，默认跳过。只有显式设置 `MEDIDIET_LLM_SMOKE_TEST=1` 和完整 LLM 环境变量时才运行。

测试人员评估 LLM 功能时应确认：

- 普通全量测试不会访问外网。
- smoke test 不发送 `patient_id`。
- LLM 失败时回退到确定性模板解释。
- LLM 输出不能改变推荐 outcome 或推荐菜单。
```

- [ ] **Step 4: Run normal tests, skip smoke, and full suite**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_llm_deepseek_smoke -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected:

- Smoke test reports 1 skipped test when env is absent.
- Full suite PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tests/test_llm_deepseek_smoke.py docs/usage.md docs/testing.md
git commit -m "test: add opt-in DeepSeek LLM smoke test"
```

---

### Task 6: Public API Exports and Main Documentation Updates

**Files:**
- Modify: `src/medidiet/__init__.py`
- Modify: `docs/api.md`
- Modify: `docs/software-design.md`
- Modify: `docs/testing.md`
- Modify: `tests/test_public_api.py`

- [ ] **Step 1: Write failing public API export assertions**

Update `tests/test_public_api.py` to also import LLM public types:

```python
    def test_llm_exports_are_available(self):
        from medidiet import (
            LLMAnswer,
            LLMConfig,
            LLMContextSanitizer,
            LLMEnhancedExplanation,
            LLMExplanationEnhancer,
            LLMFallbackReason,
            LLMQuestionAnswerer,
            MockLLMProvider,
            OpenAICompatibleLLMProvider,
        )

        self.assertEqual(LLMConfig.__name__, "LLMConfig")
        self.assertEqual(LLMFallbackReason.PROVIDER_ERROR.value, 6002)
        self.assertEqual(MockLLMProvider.__name__, "MockLLMProvider")
        self.assertEqual(OpenAICompatibleLLMProvider.__name__, "OpenAICompatibleLLMProvider")
        self.assertEqual(LLMContextSanitizer.__name__, "LLMContextSanitizer")
        self.assertEqual(LLMExplanationEnhancer.__name__, "LLMExplanationEnhancer")
        self.assertEqual(LLMQuestionAnswerer.__name__, "LLMQuestionAnswerer")
        self.assertEqual(LLMEnhancedExplanation.__name__, "LLMEnhancedExplanation")
        self.assertEqual(LLMAnswer.__name__, "LLMAnswer")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api.PublicApiTest.test_llm_exports_are_available -v
```

Expected: FAIL with `ImportError` for LLM public exports.

- [ ] **Step 3: Export LLM public API**

Modify `src/medidiet/__init__.py`:

```python
from medidiet.llm import (
    LLMAnswer,
    LLMConfig,
    LLMContextSanitizer,
    LLMEnhancedExplanation,
    LLMExplanationEnhancer,
    LLMFallbackReason,
    LLMQuestionAnswerer,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
)
```

Add these names to `__all__`:

```python
    "LLMAnswer",
    "LLMConfig",
    "LLMContextSanitizer",
    "LLMEnhancedExplanation",
    "LLMExplanationEnhancer",
    "LLMFallbackReason",
    "LLMQuestionAnswerer",
    "MockLLMProvider",
    "OpenAICompatibleLLMProvider",
```

- [ ] **Step 4: Update main documentation**

Update `docs/api.md` with:

```markdown

## 10. LLM 解释与问答 API

LLM 是推荐后的可选增强层。它不能改变 `outcome`、推荐菜单、安全事件、排除原因或评分。

公共入口：

```python
from medidiet import (
    LLMConfig,
    LLMContextSanitizer,
    LLMExplanationEnhancer,
    LLMQuestionAnswerer,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
)
```

基本用法：

```python
context = LLMContextSanitizer().sanitize(result, patient, meal_label)
provider = OpenAICompatibleLLMProvider(LLMConfig.from_env())
enhanced = LLMExplanationEnhancer(provider).enhance(context, result)
answer = LLMQuestionAnswerer(provider).answer(context, result, "为什么推荐这个餐？")
```

默认脱敏策略不会发送 `patient_id`、原始图片、地址、手机号、身份证或完整病历。
```

Update `docs/software-design.md`:

- Replace the statement that current explanations do not call LLM with a note that LLM is an optional post-processing layer.
- Add `src/medidiet/llm.py` to the module responsibility table.
- Add `LLMContextSanitizer`, `LLMExplanationEnhancer`, `LLMQuestionAnswerer`, and `OpenAICompatibleLLMProvider` to the architecture section.

Update `docs/testing.md` if Task 5 documentation did not already add LLM coverage summary.

- [ ] **Step 5: Run public API and full verification**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
git diff --check
```

Expected:

- Public API tests PASS.
- Full suite PASS.
- CLI emits trace JSON.
- `git diff --check` has no output.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/medidiet/__init__.py tests/test_public_api.py docs/api.md docs/software-design.md docs/testing.md
git commit -m "docs: expose LLM API and update architecture"
```

---

## Final Verification

After all tasks are complete, run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m unittest tests.test_llm_deepseek_smoke -v
PYTHONPATH=src python -m medidiet.cli
git status --short --branch
git log --oneline -8
```

Expected:

- Full unit suite passes.
- DeepSeek smoke test is skipped when env vars are absent.
- CLI still emits recommendation trace JSON.
- Working tree is clean except unrelated pre-existing untracked files.
- Recent commits include each task commit.

Optional real DeepSeek smoke test only when the user provides credentials and explicitly asks to run it:

```bash
MEDIDIET_LLM_SMOKE_TEST=1 \
MEDIDIET_LLM_PROVIDER=openai_compatible \
MEDIDIET_LLM_BASE_URL=https://api.deepseek.com \
MEDIDIET_LLM_API_KEY=<DEEPSEEK_API_KEY> \
MEDIDIET_LLM_MODEL=deepseek-v4 \
PYTHONPATH=src python -m unittest tests.test_llm_deepseek_smoke -v
```

## Self-Review

### Spec Coverage

- Explanation enhancement: Task 2.
- Clinician explanation enhancement: Task 2.
- Patient QA constrained to current trace: Task 3.
- Provider abstraction: Task 1.
- Mock provider: Task 2 and Task 3.
- OpenAI-compatible DeepSeek configuration path: Task 4.
- Optional real smoke test: Task 5.
- Privacy-preserving context sanitization: Task 1.
- Fallback on provider/config/output failures: Task 2 and Task 3.
- Docs updates: Task 5 and Task 6.
- Public API exposure: Task 6.

### Intentional Deferrals

- No HTTP API server.
- No persistent chatbot memory.
- No LLM image input.
- No LLM-driven ranking or meal selection.
- No automatic production logging configuration beyond safe fallback behavior.

### Placeholder Scan

This plan contains no unresolved placeholder markers. The optional real smoke test command uses `<DEEPSEEK_API_KEY>` to indicate the user-provided API key at runtime.
