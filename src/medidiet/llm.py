from __future__ import annotations

import json
import http.client
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Protocol

from medidiet.domain import CodeKind, ConceptCode, MealLabel, Nutrients, Outcome, PatientProfile, RiskLevel
from medidiet.engine import RecommendationResult


class LLMTask(str, Enum):
    EXPLANATION = "explanation"
    QUESTION_ANSWERING = "question_answering"
    RULE_EXTRACTION = "rule_extraction"
    RULE_VALIDATION = "rule_validation"


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
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.25
    send_patient_id: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_attempts <= 0:
            raise ValueError("retry_attempts must be positive")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative")

    @classmethod
    def from_env(
        cls,
        *,
        prefix: str = "MEDIDIET_LLM_",
        fallback_prefix: str | None = None,
    ) -> "LLMConfig":
        def read_env(name: str, default: str | None = None) -> str | None:
            primary = os.getenv(f"{prefix}{name}")
            if primary is not None:
                return primary
            if fallback_prefix is not None:
                fallback = os.getenv(f"{fallback_prefix}{name}")
                if fallback is not None:
                    return fallback
            return default

        timeout_raw = read_env("TIMEOUT_SECONDS", "10")
        try:
            timeout_seconds = int(timeout_raw or "10")
        except ValueError as exc:
            raise ValueError(f"{prefix}TIMEOUT_SECONDS must be an integer") from exc
        retry_attempts_raw = read_env("RETRY_ATTEMPTS", "3")
        try:
            retry_attempts = int(retry_attempts_raw or "3")
        except ValueError as exc:
            raise ValueError(f"{prefix}RETRY_ATTEMPTS must be an integer") from exc
        retry_backoff_raw = read_env("RETRY_BACKOFF_SECONDS", "0.25")
        try:
            retry_backoff_seconds = float(retry_backoff_raw or "0.25")
        except ValueError as exc:
            raise ValueError(f"{prefix}RETRY_BACKOFF_SECONDS must be a number") from exc
        return cls(
            provider=read_env("PROVIDER", "mock") or "mock",
            base_url=read_env("BASE_URL"),
            api_key=read_env("API_KEY"),
            model=read_env("MODEL"),
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            send_patient_id=False,
        )


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


@dataclass(frozen=True)
class LLMAnswer:
    answer: str
    used_fallback: bool
    fallback_reason: LLMFallbackReason | None


class LLMProviderPort(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...


class _RetryableProviderResponseError(RuntimeError):
    pass


@dataclass
class MockLLMProvider:
    explanation_payload: dict[str, object] | None = field(default=None, repr=False)
    qa_payload: dict[str, object] | None = field(default=None, repr=False)
    extraction_payload: dict[str, object] | None = field(default=None, repr=False)
    validation_payload: dict[str, object] | None = field(default=None, repr=False)
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
        elif request.task is LLMTask.RULE_EXTRACTION:
            content = json.dumps(self.extraction_payload or {}, ensure_ascii=False)
        elif request.task is LLMTask.RULE_VALIDATION:
            content = json.dumps(self.validation_payload or {}, ensure_ascii=False)
        else:
            content = json.dumps(self.qa_payload or {}, ensure_ascii=False)
        return LLMResponse(content=content, provider_name="mock", model="mock")


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
        saved_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.config.timeout_seconds)
        try:
            for attempt in range(self.config.retry_attempts):
                try:
                    response = _run_with_timeout(
                        self.config.timeout_seconds + 5,
                        lambda: urllib.request.urlopen(http_request, timeout=self.config.timeout_seconds),
                    )
                    with response:
                        raw = _run_with_timeout(self.config.timeout_seconds, lambda: response.read())
                    payload = json.loads(raw.decode("utf-8"))
                    content = payload["choices"][0]["message"]["content"]
                    if not isinstance(content, str):
                        raise _RetryableProviderResponseError("LLM provider message content must be a string")
                    if not content.strip():
                        raise _RetryableProviderResponseError("LLM provider message content was empty")
                    return LLMResponse(
                        content=content,
                        provider_name="openai_compatible",
                        model=self.config.model,
                    )
                except urllib.error.HTTPError as exc:
                    if not _is_retryable_http_error(exc) or attempt == self.config.retry_attempts - 1:
                        raise RuntimeError("LLM provider request failed") from exc
                    _sleep_before_retry(self.config.retry_backoff_seconds, attempt)
                except (
                    urllib.error.URLError,
                    TimeoutError,
                    http.client.IncompleteRead,
                    json.JSONDecodeError,
                    KeyError,
                    IndexError,
                    TypeError,
                    _RetryableProviderResponseError,
                ) as exc:
                    if attempt == self.config.retry_attempts - 1:
                        raise RuntimeError("LLM provider request failed") from exc
                    _sleep_before_retry(self.config.retry_backoff_seconds, attempt)
            raise RuntimeError("LLM provider request failed")
        finally:
            socket.setdefaulttimeout(saved_timeout)


def _is_retryable_http_error(exc: urllib.error.HTTPError) -> bool:
    return exc.code in {408, 409, 425, 429, 500, 502, 503, 504}


def _sleep_before_retry(backoff_seconds: float, attempt: int) -> None:
    if backoff_seconds:
        time.sleep(backoff_seconds * (2**attempt))


def _run_with_timeout(timeout_seconds: int, fn: "object") -> object:
    """Run fn() in a daemon thread, raise TimeoutError if it exceeds timeout."""
    result: list[object] = [None]
    error: list[Exception | None] = [None]
    done = threading.Event()

    def _worker() -> None:
        try:
            result[0] = fn()  # type: ignore[call-arg]
        except Exception as exc:
            error[0] = exc
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    if not done.wait(timeout=timeout_seconds):
        raise TimeoutError(f"Operation timed out after {timeout_seconds}s")
    if error[0] is not None:
        raise error[0]
    return result[0]


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
        clinician_explanation_text = _clinician_explanation_to_text(clinician_explanation)
        if not isinstance(patient_explanation, str) or clinician_explanation_text is None:
            return _fallback_explanation(result, LLMFallbackReason.MISSING_FIELD)
        if not patient_explanation.strip() or not clinician_explanation_text.strip():
            return _fallback_explanation(result, LLMFallbackReason.EMPTY_OUTPUT)
        if _contains_unsafe_explanation(patient_explanation, clinician_explanation_text, context.outcome):
            return _fallback_explanation(result, LLMFallbackReason.UNSAFE_OUTPUT)

        return LLMEnhancedExplanation(
            patient_explanation=patient_explanation,
            clinician_explanation=clinician_explanation_text,
            used_fallback=False,
            fallback_reason=None,
        )


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
            system_prompt=_EXPLANATION_SYSTEM_PROMPT,
            user_prompt=_qa_user_prompt(context, result, question),
        )
        try:
            response = self.provider.complete(request)
        except Exception:
            return _fallback_answer(LLMFallbackReason.PROVIDER_ERROR)

        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError:
            return _fallback_answer(LLMFallbackReason.INVALID_JSON)

        if not isinstance(payload, dict):
            return _fallback_answer(LLMFallbackReason.INVALID_JSON)

        answer = payload.get("answer")
        if not isinstance(answer, str):
            return _fallback_answer(LLMFallbackReason.MISSING_FIELD)
        if not answer.strip():
            return _fallback_answer(LLMFallbackReason.EMPTY_OUTPUT)
        if _contains_unsafe_explanation(answer, "", context.outcome):
            return _fallback_answer(LLMFallbackReason.UNSAFE_OUTPUT)

        return LLMAnswer(answer=answer.strip(), used_fallback=False, fallback_reason=None)


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
_OUT_OF_SCOPE_ANSWER = "这个问题超出了本次餐食推荐解释范围，请咨询营养师或医生。"
_GENERAL_QA_FALLBACK_ANSWER = "暂时无法使用大模型回答，我只能基于当前推荐结果说明：请遵循页面中的安全提示和营养师建议。"

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


_OUT_OF_SCOPE_QUESTION_MARKERS = (
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


def _fallback_explanation(
    result: RecommendationResult,
    reason: LLMFallbackReason,
) -> LLMEnhancedExplanation:
    clinician_explanation = _FALLBACK_CLINICIAN_EXPLANATION
    # Preserve knowledge snippets from the deterministic clinician payload
    # so they remain available when LLM enhancement falls back.
    if isinstance(result.clinician_explanation, dict):
        snippets = result.clinician_explanation.get("knowledgeSnippets")
        if snippets:
            snippets_json = json.dumps(snippets, ensure_ascii=False)
            clinician_explanation = (
                f"{_FALLBACK_CLINICIAN_EXPLANATION}\n\n"
                f"knowledgeSnippets: {snippets_json}"
            )
    return LLMEnhancedExplanation(
        patient_explanation=result.patient_explanation,
        clinician_explanation=clinician_explanation,
        used_fallback=True,
        fallback_reason=reason,
    )


def _clinician_explanation_to_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return None


def _fallback_answer(reason: LLMFallbackReason) -> LLMAnswer:
    if reason is LLMFallbackReason.OUT_OF_SCOPE_QUESTION:
        answer = _OUT_OF_SCOPE_ANSWER
    else:
        answer = _GENERAL_QA_FALLBACK_ANSWER
    return LLMAnswer(answer=answer, used_fallback=True, fallback_reason=reason)


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


def _qa_user_prompt(context: LLMRecommendationContext, result: RecommendationResult, question: str) -> str:
    return json.dumps(
        {
            "task": "answer_recommendation_question",
            "question": question,
            "context": context.to_dict(),
            "outcome": result.outcome.name,
            "requiredOutput": {
                "answer": "Chinese answer constrained to the current recommendation result",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _is_out_of_scope_question(question: str) -> bool:
    lowered = question.lower()
    return any(marker in lowered for marker in _OUT_OF_SCOPE_QUESTION_MARKERS)


def _contains_unsafe_explanation(
    patient_explanation: str,
    clinician_explanation: str,
    outcome: Outcome,
) -> bool:
    text = f"{patient_explanation}\n{clinician_explanation}".lower()
    if any(phrase in text for phrase in _UNSAFE_EXPLANATION_PHRASES):
        return True
    if outcome is Outcome.REFUSED and _contains_final_decision_override(text):
        return True
    if outcome is Outcome.HUMAN_REVIEW_REQUIRED and (
        ("无需" in text and "审核" in text)
        or _contains_final_decision_override(text)
        or "可以直接吃" in text
        or "no review needed" in text
        or "review not needed" in text
    ):
        return True
    return False


def _contains_final_decision_override(text: str) -> bool:
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
