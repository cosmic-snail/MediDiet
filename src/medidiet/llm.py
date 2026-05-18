from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Protocol

from medidiet.domain import CodeKind, ConceptCode, MealLabel, Nutrients, Outcome, PatientProfile, RiskLevel
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
    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    timeout_seconds: int = 10
    send_patient_id: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class LLMRequest:
    task: LLMTask
    system_prompt: str = field(repr=False)
    user_prompt: str = field(repr=False)
    response_format: str = "json"

    def __post_init__(self) -> None:
        if not isinstance(self.task, LLMTask):
            raise TypeError("task must be an LLMTask")


@dataclass(frozen=True)
class LLMResponse:
    content: str = field(repr=False)
    provider_name: str
    model: str


@dataclass(frozen=True)
class LLMEnhancedExplanation:
    patient_explanation: str
    clinician_explanation: str
    used_fallback: bool
    fallback_reason: LLMFallbackReason | None


class LLMProviderPort(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...


@dataclass
class MockLLMProvider:
    explanation_payload: dict[str, object] | None = field(default=None, repr=False)
    qa_payload: dict[str, object] | None = field(default=None, repr=False)
    raw_content: str | None = field(default=None, repr=False)
    error: Exception | None = field(default=None, repr=False)
    requests: list[LLMRequest] = field(default_factory=list, repr=False)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.raw_content is not None:
            content = self.raw_content
        elif request.task is LLMTask.EXPLANATION:
            content = json.dumps(self.explanation_payload or {}, ensure_ascii=False)
        else:
            content = json.dumps(self.qa_payload or {}, ensure_ascii=False)
        return LLMResponse(content=content, provider_name="mock", model="mock")


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
            conditions=tuple(sorted(patient.conditions, key=_concept_sort_key)),
            allergens=tuple(sorted(patient.allergens, key=_concept_sort_key)),
            meal_label=meal_label,
            selected_item_name=selected_item.name if selected_item is not None else None,
            selected_item_nutrients=selected_item.nutrients if selected_item is not None else None,
            safety_event_codes=tuple(event.code.value for event in result.trace.safety_events),
            exclusion_codes=tuple(rejection.code.value for rejection in result.trace.exclusions.values()),
            matched_nutrition_tags=_matched_tags_from_payload(matched_tags),
            patient_explanation=_redact_sensitive_text(result.patient_explanation, patient.patient_id),
            clinician_explanation=_strip_sensitive_payload(result.clinician_explanation, patient.patient_id),
        )


class LLMExplanationEnhancer:
    def __init__(self, provider: LLMProviderPort | None):
        self.provider = provider

    def enhance(
        self,
        context: LLMRecommendationContext,
        result: RecommendationResult,
    ) -> LLMEnhancedExplanation:
        if self.provider is None:
            return _fallback_explanation(result, LLMFallbackReason.PROVIDER_NOT_CONFIGURED)

        request = LLMRequest(
            task=LLMTask.EXPLANATION,
            system_prompt=_EXPLANATION_SYSTEM_PROMPT,
            user_prompt=_explanation_user_prompt(context),
        )
        try:
            response = self.provider.complete(request)
        except Exception:
            return _fallback_explanation(result, LLMFallbackReason.PROVIDER_ERROR)

        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError:
            return _fallback_explanation(result, LLMFallbackReason.INVALID_JSON)

        if not isinstance(payload, dict):
            return _fallback_explanation(result, LLMFallbackReason.INVALID_JSON)

        patient_explanation = payload.get("patientExplanation")
        clinician_explanation = payload.get("clinicianExplanation")
        if not isinstance(patient_explanation, str) or not isinstance(clinician_explanation, str):
            return _fallback_explanation(result, LLMFallbackReason.MISSING_FIELD)
        if not patient_explanation.strip() or not clinician_explanation.strip():
            return _fallback_explanation(result, LLMFallbackReason.EMPTY_OUTPUT)
        if _contains_unsafe_explanation(patient_explanation, clinician_explanation, context.outcome):
            return _fallback_explanation(result, LLMFallbackReason.UNSAFE_OUTPUT)

        return LLMEnhancedExplanation(
            patient_explanation=patient_explanation,
            clinician_explanation=clinician_explanation,
            used_fallback=False,
            fallback_reason=None,
        )


def _matched_tags_from_payload(payload: object) -> tuple[ConceptCode, ...]:
    if not isinstance(payload, list | tuple):
        return ()
    tags: list[ConceptCode] = []
    for item in payload:
        if (
            isinstance(item, dict)
            and item.get("kind") == CodeKind.NUTRITION_TAG.value
            and isinstance(item.get("value"), str)
        ):
            tags.append(ConceptCode(CodeKind.NUTRITION_TAG, item["value"]))
    return tuple(tags)


def _concept_to_dict(code: ConceptCode) -> dict[str, str]:
    return {"kind": code.kind.value, "value": code.value, _camel_case(code.kind.value): code.value}


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


def _concept_sort_key(code: ConceptCode) -> tuple[str, str]:
    return (code.kind.value, code.value)


def _camel_case(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


def _strip_sensitive_payload(payload: object, patient_id: str) -> object:
    if isinstance(payload, dict):
        return {
            key: _strip_sensitive_payload(value, patient_id)
            for key, value in payload.items()
            if key not in {"patientId", "patient_id"}
        }
    if isinstance(payload, list):
        return [_strip_sensitive_payload(item, patient_id) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_strip_sensitive_payload(item, patient_id) for item in payload)
    if isinstance(payload, str):
        return _redact_sensitive_text(payload, patient_id)
    return payload


def _redact_sensitive_text(text: str, patient_id: str) -> str:
    if not patient_id:
        return text
    return text.replace(patient_id, "[redacted]")


_EXPLANATION_SYSTEM_PROMPT = """You enhance explanations for a completed rules-based diet recommendation.
Safety boundaries:
- The rules-based recommendation is already completed.
- You cannot change the outcome.
- You cannot recommend excluded or unsafe items.
- You cannot ignore allergies, contraindications, clinician review, or safety warnings.
- Do not provide diagnosis, medication, or treatment advice.
- Use only the provided context.
- Return JSON only."""

_FALLBACK_CLINICIAN_EXPLANATION = "LLM enhancement unavailable; deterministic template explanation was used."

_UNSAFE_EXPLANATION_PHRASES = (
    "忽略过敏",
    "忽略禁忌",
    "无需营养师",
    "无需医生",
    "不用人工审核",
    "自行调整药",
    "停药",
    "ignore allergy",
    "ignore allergies",
    "ignore contraindication",
    "ignore contraindications",
    "ignore clinician",
    "adjust medication",
    "directly eat",
)


def _fallback_explanation(
    result: RecommendationResult,
    reason: LLMFallbackReason,
) -> LLMEnhancedExplanation:
    return LLMEnhancedExplanation(
        patient_explanation=result.patient_explanation,
        clinician_explanation=_FALLBACK_CLINICIAN_EXPLANATION,
        used_fallback=True,
        fallback_reason=reason,
    )


def _explanation_user_prompt(context: LLMRecommendationContext) -> str:
    return json.dumps(
        {
            "task": "explain_recommendation",
            "context": context.to_dict(),
            "requiredOutputFields": ["patientExplanation", "clinicianExplanation"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _contains_unsafe_explanation(
    patient_explanation: str,
    clinician_explanation: str,
    outcome: Outcome,
) -> bool:
    text = f"{patient_explanation}\n{clinician_explanation}".lower()
    if any(phrase in text for phrase in _UNSAFE_EXPLANATION_PHRASES):
        return True
    if outcome is Outcome.REFUSED and _contains_refused_outcome_override(text):
        return True
    if outcome is Outcome.HUMAN_REVIEW_REQUIRED and (
        ("无需" in text and "审核" in text)
        or "可以直接吃" in text
        or "no review needed" in text
        or "review not needed" in text
    ):
        return True
    return False


def _contains_refused_outcome_override(text: str) -> bool:
    if "推荐成功" in text or "可以放心吃" in text or "safe to eat" in text:
        return True
    return any(
        phrase in text
        for phrase in (
            "is recommended",
            "recommended for",
            "we recommend",
            "i recommend",
            "recommend this",
            "converted into a recommendation",
        )
    )
