from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum

from medidiet.domain import CodeKind, ConceptCode, IntakeRecord, Nutrients
from medidiet.rules import LimitScope, NutrientLimit, NutrientMetric, RulePack


class NutritionReason(IntEnum):
    PER_MEAL_LIMIT = 3001
    DAILY_LIMIT_REMAINING = 3002
    ROLLING_LIMIT_REMAINING = 3003


@dataclass(frozen=True)
class DailyNutritionState:
    total: Nutrients
    low_confidence_labels: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RemainingNutrientLimit:
    metric: NutrientMetric
    scope: LimitScope
    limit_value: float
    consumed_value: float
    remaining_value: float
    reason: NutritionReason
    window_hours: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric, NutrientMetric):
            raise TypeError("metric must be a NutrientMetric")
        if not isinstance(self.scope, LimitScope):
            raise TypeError("scope must be a LimitScope")
        if not isinstance(self.reason, NutritionReason):
            raise TypeError("reason must be a NutritionReason")


@dataclass(frozen=True)
class NextMealTarget:
    limits: tuple[RemainingNutrientLimit, ...] = field(default_factory=tuple)
    preferred_tags: frozenset[ConceptCode] = field(default_factory=frozenset)

    def find_limit(self, metric: NutrientMetric, scope: LimitScope) -> RemainingNutrientLimit:
        for limit in self.limits:
            if limit.metric is metric and limit.scope is scope:
                return limit
        raise ValueError(f"limit not found: {metric.value}:{scope.value}")


class DailyNutritionCalculator:
    def __init__(
        self,
        rule_pack: RulePack,
        confidence_threshold: float = 0.7,
        now: datetime | None = None,
    ):
        self.rule_pack = rule_pack
        self.confidence_threshold = confidence_threshold
        self.now = now or datetime.now(timezone.utc)

    # Thresholds for previous-meal nutrient gap detection
    _PROTEIN_GAP_THRESHOLD_G = 15.0
    _FIBER_GAP_THRESHOLD_G = 3.0

    def compensation_tags(
        self,
        previous_meal_records: list[IntakeRecord],
    ) -> set[ConceptCode]:
        """Return nutrition tags to compensate for previous meal deficiencies.

        Uses direct ConceptCode construction (not require()) so that
        compensation works even when the rule pack's concept registry
        doesn't pre-register these standard nutrition tags.
        """
        tags: set[ConceptCode] = set()
        if not previous_meal_records:
            return tags
        total = Nutrients()
        for r in previous_meal_records:
            total += r.nutrients
        if total.protein_g < self._PROTEIN_GAP_THRESHOLD_G:
            tags.add(ConceptCode(CodeKind.NUTRITION_TAG, "lean_protein"))
        if total.fiber_g < self._FIBER_GAP_THRESHOLD_G:
            tags.add(ConceptCode(CodeKind.NUTRITION_TAG, "high_fiber"))
        return tags

    def aggregate(self, records: list[IntakeRecord]) -> DailyNutritionState:
        total = Nutrients()
        low_confidence_labels: list[str] = []
        for record in records:
            total += record.nutrients
            if record.confidence.is_low(self.confidence_threshold) and not record.manually_corrected:
                low_confidence_labels.append(record.food_label)
        return DailyNutritionState(total=total, low_confidence_labels=tuple(low_confidence_labels))

    def next_meal_target(self, conditions: set[ConceptCode], records: list[IntakeRecord]) -> NextMealTarget:
        preferred_tags: set[ConceptCode] = set()
        remaining_limits: list[RemainingNutrientLimit] = []

        for condition in conditions:
            rule = self.rule_pack.for_condition(condition)
            preferred_tags.update(rule.preferred_tags)
            for limit in rule.nutrition_limits:
                remaining_limits.append(self._remaining_limit(limit, records))

        return NextMealTarget(limits=tuple(remaining_limits), preferred_tags=frozenset(preferred_tags))

    def _remaining_limit(self, limit: NutrientLimit, records: list[IntakeRecord]) -> RemainingNutrientLimit:
        consumed_value = self._consumed_for_limit(limit, records)
        remaining_value = max(limit.max_value - consumed_value, 0)
        reason_by_scope = {
            LimitScope.PER_MEAL: NutritionReason.PER_MEAL_LIMIT,
            LimitScope.DAILY: NutritionReason.DAILY_LIMIT_REMAINING,
            LimitScope.ROLLING_WINDOW: NutritionReason.ROLLING_LIMIT_REMAINING,
        }
        return RemainingNutrientLimit(
            metric=limit.metric,
            scope=limit.scope,
            limit_value=limit.max_value,
            consumed_value=consumed_value,
            remaining_value=remaining_value,
            reason=reason_by_scope[limit.scope],
            window_hours=limit.window_hours,
        )

    def _consumed_for_limit(self, limit: NutrientLimit, records: list[IntakeRecord]) -> float:
        if limit.scope is LimitScope.PER_MEAL:
            return 0
        if limit.scope is LimitScope.DAILY:
            relevant_records = [record for record in records if _is_same_day(record.occurred_at, self.now)]
        else:
            window_start = self.now - timedelta(hours=limit.window_hours or 0)
            relevant_records = [record for record in records if window_start <= record.occurred_at <= self.now]
        return sum(_nutrient_value(record.nutrients, limit.metric) for record in relevant_records)


def _is_same_day(left: datetime, right: datetime) -> bool:
    return left.astimezone(timezone.utc).date() == right.astimezone(timezone.utc).date()


def _nutrient_value(nutrients: Nutrients, metric: NutrientMetric) -> float:
    field_by_metric = {
        NutrientMetric.ENERGY_KCAL: "energy_kcal",
        NutrientMetric.CARBS_G: "carbs_g",
        NutrientMetric.FAT_G: "fat_g",
        NutrientMetric.SODIUM_MG: "sodium_mg",
        NutrientMetric.SUGAR_G: "sugar_g",
    }
    return getattr(nutrients, field_by_metric[metric])
