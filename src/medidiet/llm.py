from __future__ import annotations

from dataclasses import dataclass
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
        ...


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
