from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from medidiet.domain import IntakeRecord, MealLabel, MenuItem, PatientProfile


@dataclass(frozen=True)
class RecommendationRequestEnvelope:
    schema_version: str
    source_system: str
    source_version: str
    request_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_aware_datetime("created_at", self.created_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "sourceSystem": self.source_system,
            "sourceVersion": self.source_version,
            "requestId": self.request_id,
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class IntakeEstimationRequest:
    envelope: RecommendationRequestEnvelope
    image_uri: str
    meal_label: MealLabel

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, RecommendationRequestEnvelope):
            raise TypeError("envelope must be a RecommendationRequestEnvelope")
        if not isinstance(self.meal_label, MealLabel):
            raise TypeError("meal_label must be a MealLabel")

    def to_dict(self) -> dict[str, object]:
        return {
            "envelope": self.envelope.to_dict(),
            "imageUri": self.image_uri,
            "mealLabel": self.meal_label.value,
        }


class EventName(str, Enum):
    RECOMMENDATION_REQUESTED = "RecommendationRequested"
    RECOMMENDATION_COMPLETED = "RecommendationCompleted"
    HUMAN_REVIEW_REQUIRED = "HumanReviewRequired"
    HUMAN_REVIEW_COMPLETED = "HumanReviewCompleted"
    PATIENT_PREFERENCE_UPDATED = "PatientPreferenceUpdated"
    INTAKE_RECORD_CORRECTED = "IntakeRecordCorrected"
    MENU_NUTRITION_ANNOTATED = "MenuNutritionAnnotated"
    RULE_PACK_PUBLISHED = "RulePackPublished"
    RULE_PACK_ROLLED_BACK = "RulePackRolledBack"


@dataclass(frozen=True)
class DomainEvent:
    name: EventName
    trace_id: str
    payload: dict[str, object]
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.name, EventName):
            raise TypeError("name must be an EventName")
        _require_aware_datetime("created_at", self.created_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "traceId": self.trace_id,
            "payload": self.payload,
            "createdAt": self.created_at.isoformat(),
        }


class IntakeEstimatorPort(Protocol):
    def estimate(self, request: IntakeEstimationRequest) -> list[IntakeRecord]:
        raise NotImplementedError


class MenuProviderPort(Protocol):
    def candidate_items(self, envelope: RecommendationRequestEnvelope, patient: PatientProfile) -> list[MenuItem]:
        raise NotImplementedError


class PatientContextPort(Protocol):
    def load_patient(self, envelope: RecommendationRequestEnvelope, patient_id: str) -> PatientProfile:
        raise NotImplementedError


class EventPublisherPort(Protocol):
    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError


def _require_aware_datetime(field_name: str, value: datetime) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
