from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from medidiet.domain import ConceptCode, MenuItem, Preference
from medidiet.planner import MealPlan
from medidiet.rules import LimitScope, NutrientMetric


class MatchRejectionCode(IntEnum):
    UNAVAILABLE = 5001
    AVOID_TAG = 5002
    NUTRIENT_LIMIT_EXCEEDED = 5003


@dataclass(frozen=True)
class MatchRejection:
    code: MatchRejectionCode
    item_id: str
    concept: ConceptCode | None = None
    metric: NutrientMetric | None = None
    scope: LimitScope | None = None
    measured_value: float | None = None
    limit_value: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, MatchRejectionCode):
            raise TypeError("code must be a MatchRejectionCode")


@dataclass(frozen=True)
class MenuItemScore:
    item: MenuItem
    score: float
    matched_required_tags: frozenset[ConceptCode] = field(default_factory=frozenset)
    matched_taste_tags: frozenset[ConceptCode] = field(default_factory=frozenset)


@dataclass(frozen=True)
class MatchResult:
    accepted: tuple[MenuItemScore, ...]
    excluded: dict[str, MatchRejection]


class MenuMatcher:
    def match(self, plan: MealPlan, candidates: list[MenuItem], preference: Preference) -> MatchResult:
        accepted: list[MenuItemScore] = []
        excluded: dict[str, MatchRejection] = {}

        for candidate in candidates:
            rejection = self._reject(plan, candidate)
            if rejection is not None:
                excluded[candidate.item_id] = rejection
                continue
            accepted.append(self._score(plan, candidate, preference))

        accepted.sort(key=lambda item_score: item_score.score, reverse=True)
        return MatchResult(accepted=tuple(accepted), excluded=excluded)

    def _reject(self, plan: MealPlan, candidate: MenuItem) -> MatchRejection | None:
        if not candidate.available:
            return MatchRejection(code=MatchRejectionCode.UNAVAILABLE, item_id=candidate.item_id)

        for avoid_tag in plan.avoid_tags:
            if avoid_tag in candidate.contraindication_tags:
                return MatchRejection(
                    code=MatchRejectionCode.AVOID_TAG,
                    item_id=candidate.item_id,
                    concept=avoid_tag,
                )

        for limit in plan.limits:
            if limit.scope is not LimitScope.PER_MEAL:
                continue
            measured_value = _nutrient_value(candidate, limit.metric)
            if measured_value > limit.remaining_value:
                return MatchRejection(
                    code=MatchRejectionCode.NUTRIENT_LIMIT_EXCEEDED,
                    item_id=candidate.item_id,
                    metric=limit.metric,
                    scope=limit.scope,
                    measured_value=measured_value,
                    limit_value=limit.remaining_value,
                )

        return None

    def _score(self, plan: MealPlan, candidate: MenuItem, preference: Preference) -> MenuItemScore:
        matched_required_tags = frozenset(plan.required_tags.intersection(candidate.nutrition_tags))
        matched_taste_tags = frozenset(preference.taste_tags.intersection(candidate.taste_tags))
        score = 0.0
        score += 10 * len(matched_required_tags)
        score += 4 * len(matched_taste_tags)
        score += 3 * candidate.merchant_reliability
        if preference.max_price_cents is not None and candidate.price_cents <= preference.max_price_cents:
            score += 2
        if preference.max_distance_meters is not None and candidate.distance_meters <= preference.max_distance_meters:
            score += 2
        score += max(0, 2 - candidate.price_cents / 5000)
        score += max(0, 2 - candidate.distance_meters / 3000)
        return MenuItemScore(
            item=candidate,
            score=round(score, 4),
            matched_required_tags=matched_required_tags,
            matched_taste_tags=matched_taste_tags,
        )


def _nutrient_value(item: MenuItem, metric: NutrientMetric) -> float:
    field_by_metric = {
        NutrientMetric.ENERGY_KCAL: "energy_kcal",
        NutrientMetric.CARBS_G: "carbs_g",
        NutrientMetric.FAT_G: "fat_g",
        NutrientMetric.SODIUM_MG: "sodium_mg",
        NutrientMetric.SUGAR_G: "sugar_g",
    }
    return getattr(item.nutrients, field_by_metric[metric])
