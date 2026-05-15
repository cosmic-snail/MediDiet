from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from medidiet.domain import CodeKind, ConceptCode, IntakeRecord, MenuItem, PatientProfile
from medidiet.rules import LimitScope, NutrientLimit, NutrientMetric, RulePack


class SafetyCode(IntEnum):
    OUT_OF_SCOPE_NON_ADULT = 1001
    ALLERGY_MATCH = 1002
    CONTRAINDICATION_MATCH = 1003
    NUTRIENT_LIMIT_EXCEEDED = 1004
    PATIENT_PROFILE_UNCONFIRMED = 2001
    LOW_CONFIDENCE_INTAKE = 2002
    LOW_CONFIDENCE_MENU = 2003


class SafetySeverity(IntEnum):
    HARD_BLOCK = 1
    UNCERTAINTY = 2


@dataclass(frozen=True)
class SafetyEvent:
    code: SafetyCode
    severity: SafetySeverity
    patient_id: str
    entity_id: str | None = None
    concept: ConceptCode | None = None
    metric: NutrientMetric | None = None
    scope: LimitScope | None = None
    measured_value: float | None = None
    limit_value: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, SafetyCode):
            raise TypeError("code must be a SafetyCode")
        if not isinstance(self.severity, SafetySeverity):
            raise TypeError("severity must be a SafetySeverity")


@dataclass(frozen=True)
class SafetyResult:
    hard_blocks: tuple[SafetyEvent, ...] = field(default_factory=tuple)
    uncertainties: tuple[SafetyEvent, ...] = field(default_factory=tuple)

    @property
    def requires_human_review(self) -> bool:
        return bool(self.hard_blocks or self.uncertainties)


class SafetyGate:
    def __init__(
        self,
        rule_pack: RulePack,
        confidence_threshold: float = 0.7,
        log_file_path: str | Path | None = None,
    ):
        self.rule_pack = rule_pack
        self.confidence_threshold = confidence_threshold
        self.logger = _build_logger(log_file_path) if log_file_path is not None else logging.getLogger("medidiet.safety")

    def evaluate(
        self,
        patient: PatientProfile,
        menu_items: list[MenuItem],
        intake_records: list[IntakeRecord] | None = None,
    ) -> SafetyResult:
        hard_blocks: list[SafetyEvent] = []
        uncertainties: list[SafetyEvent] = []
        intake_records = intake_records or []

        if not patient.is_adult():
            hard_blocks.append(
                SafetyEvent(
                    code=SafetyCode.OUT_OF_SCOPE_NON_ADULT,
                    severity=SafetySeverity.HARD_BLOCK,
                    patient_id=patient.patient_id,
                )
            )
        if not patient.key_risk_fields_confirmed:
            uncertainties.append(
                SafetyEvent(
                    code=SafetyCode.PATIENT_PROFILE_UNCONFIRMED,
                    severity=SafetySeverity.UNCERTAINTY,
                    patient_id=patient.patient_id,
                )
            )

        for record in intake_records:
            if record.confidence.is_low(self.confidence_threshold) and not record.manually_corrected:
                uncertainties.append(
                    SafetyEvent(
                        code=SafetyCode.LOW_CONFIDENCE_INTAKE,
                        severity=SafetySeverity.UNCERTAINTY,
                        patient_id=patient.patient_id,
                        entity_id=record.food_label,
                    )
                )

        for item in menu_items:
            if item.nutrition_confidence.is_low(self.confidence_threshold):
                uncertainties.append(
                    SafetyEvent(
                        code=SafetyCode.LOW_CONFIDENCE_MENU,
                        severity=SafetySeverity.UNCERTAINTY,
                        patient_id=patient.patient_id,
                        entity_id=item.item_id,
                    )
                )
            for allergen in patient.allergens:
                if item.contains_allergen(allergen):
                    hard_blocks.append(
                        SafetyEvent(
                            code=SafetyCode.ALLERGY_MATCH,
                            severity=SafetySeverity.HARD_BLOCK,
                            patient_id=patient.patient_id,
                            entity_id=item.item_id,
                            concept=allergen,
                        )
                    )
            for condition in patient.conditions:
                rule = self.rule_pack.rules_by_condition.get(condition)
                if rule is None:
                    continue
                hard_blocks.extend(self._condition_hard_blocks(patient, item, rule.hard_exclusions))
                hard_blocks.extend(self._nutrient_limit_hard_blocks(patient, item, rule.nutrition_limits))

        self._log_events(hard_blocks)
        self._log_events(uncertainties)
        return SafetyResult(hard_blocks=tuple(hard_blocks), uncertainties=tuple(uncertainties))

    def _condition_hard_blocks(
        self,
        patient: PatientProfile,
        item: MenuItem,
        hard_exclusions: frozenset[ConceptCode],
    ) -> list[SafetyEvent]:
        events: list[SafetyEvent] = []
        for contraindication in patient.contraindications:
            if contraindication in hard_exclusions:
                events.append(
                    SafetyEvent(
                        code=SafetyCode.CONTRAINDICATION_MATCH,
                        severity=SafetySeverity.HARD_BLOCK,
                        patient_id=patient.patient_id,
                        entity_id=item.item_id,
                        concept=contraindication,
                    )
                )
        return events

    def _nutrient_limit_hard_blocks(
        self,
        patient: PatientProfile,
        item: MenuItem,
        limits: frozenset[NutrientLimit],
    ) -> list[SafetyEvent]:
        events: list[SafetyEvent] = []
        for limit in limits:
            if limit.scope is not LimitScope.PER_MEAL:
                continue
            measured_value = _nutrient_value(item, limit.metric)
            if measured_value > limit.max_value:
                events.append(
                    SafetyEvent(
                        code=SafetyCode.NUTRIENT_LIMIT_EXCEEDED,
                        severity=SafetySeverity.HARD_BLOCK,
                        patient_id=patient.patient_id,
                        entity_id=item.item_id,
                        metric=limit.metric,
                        scope=limit.scope,
                        measured_value=measured_value,
                        limit_value=limit.max_value,
                    )
                )
        return events

    def _log_events(self, events: list[SafetyEvent]) -> None:
        for event in events:
            self.logger.warning(_format_event(self.rule_pack.version, event))


def _build_logger(log_file_path: str | Path) -> logging.Logger:
    path = Path(log_file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"medidiet.safety.{path}")
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    logger.handlers.clear()
    handler = logging.FileHandler(path)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s pid=%(process)d tid=%(thread)d %(message)s"))
    logger.addHandler(handler)
    return logger


def _format_event(rule_pack_version: str, event: SafetyEvent) -> str:
    fields = {
        "event": "safety_event",
        "code": event.code.value,
        "code_name": event.code.name,
        "severity": event.severity.name.lower(),
        "patient_id": event.patient_id,
        "entity_id": event.entity_id,
        "concept_kind": event.concept.kind.value if event.concept else None,
        "concept_value": event.concept.value if event.concept else None,
        "metric": event.metric.value if event.metric else None,
        "scope": event.scope.value if event.scope else None,
        "measured_value": event.measured_value,
        "limit_value": event.limit_value,
        "rule_pack_version": rule_pack_version,
    }
    return " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)


def _nutrient_value(item: MenuItem, metric: NutrientMetric) -> float:
    field_by_metric = {
        NutrientMetric.ENERGY_KCAL: "energy_kcal",
        NutrientMetric.CARBS_G: "carbs_g",
        NutrientMetric.FAT_G: "fat_g",
        NutrientMetric.SODIUM_MG: "sodium_mg",
        NutrientMetric.SUGAR_G: "sugar_g",
    }
    return getattr(item.nutrients, field_by_metric[metric])
