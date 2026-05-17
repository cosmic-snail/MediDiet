from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry


class NutrientMetric(str, Enum):
    ENERGY_KCAL = "energy_kcal"
    CARBS_G = "carbs_g"
    FAT_G = "fat_g"
    SODIUM_MG = "sodium_mg"
    SUGAR_G = "sugar_g"


class LimitScope(str, Enum):
    PER_MEAL = "per_meal"
    DAILY = "daily"
    ROLLING_WINDOW = "rolling_window"


@dataclass(frozen=True)
class NutrientLimit:
    metric: NutrientMetric
    scope: LimitScope
    max_value: float
    window_hours: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric, NutrientMetric):
            raise TypeError("metric must be a NutrientMetric")
        if not isinstance(self.scope, LimitScope):
            raise TypeError("scope must be a LimitScope")
        if not isinstance(self.max_value, int | float) or isinstance(self.max_value, bool):
            raise ValueError("max_value must be a finite positive number")
        if not isfinite(self.max_value) or self.max_value <= 0 or self.max_value > 1_000_000:
            raise ValueError("max_value must be a finite positive number")
        if self.scope is LimitScope.ROLLING_WINDOW:
            if not isinstance(self.window_hours, int) or isinstance(self.window_hours, bool) or self.window_hours <= 0:
                raise ValueError("rolling window limits require positive integer window_hours")
        elif self.window_hours is not None:
            raise ValueError("window_hours is only valid for rolling window limits")


@dataclass(frozen=True)
class RuleSource:
    title: str
    url: str
    version: str
    note: str = "baseline demo threshold; pending clinician approval"


@dataclass(frozen=True)
class ConditionRule:
    condition: ConceptCode
    hard_exclusions: set[ConceptCode]
    preferred_tags: set[ConceptCode]
    nutrition_limits: set[NutrientLimit]

    def __post_init__(self) -> None:
        _require_code_kind("condition", self.condition, CodeKind.CONDITION)
        _require_code_set("hard_exclusions", self.hard_exclusions, CodeKind.CONTRAINDICATION)
        _require_code_set("preferred_tags", self.preferred_tags, CodeKind.NUTRITION_TAG)
        for limit in self.nutrition_limits:
            if not isinstance(limit, NutrientLimit):
                raise TypeError("nutrition_limits must contain NutrientLimit values")
        object.__setattr__(self, "hard_exclusions", frozenset(self.hard_exclusions))
        object.__setattr__(self, "preferred_tags", frozenset(self.preferred_tags))
        object.__setattr__(self, "nutrition_limits", frozenset(self.nutrition_limits))


@dataclass(frozen=True)
class RulePack:
    version: str
    sources: tuple[RuleSource, ...]
    concepts: ConceptRegistry
    rules_by_condition: dict[ConceptCode, ConditionRule]

    def for_condition(self, condition: ConceptCode) -> ConditionRule:
        _require_code_kind("condition", condition, CodeKind.CONDITION)
        if condition not in self.rules_by_condition:
            raise ValueError(f"no rule for condition: {condition.value}")
        return self.rules_by_condition[condition]


def load_baseline_rule_pack() -> RulePack:
    concepts = _baseline_concepts()
    sources = (
        RuleSource(
            title="Chinese Dietary Guidelines",
            url="https://dg.cnsoc.org/",
            version="2022",
        ),
        RuleSource(
            title="Adult Hypertension Dietary Guidance",
            url="https://www.nhc.gov.cn/",
            version="2023",
        ),
        RuleSource(
            title="Adult Diabetes Dietary Guidance",
            url="https://www.nhc.gov.cn/",
            version="2023",
        ),
        RuleSource(
            title="Adult Hyperlipidemia Dietary Guidance",
            url="https://www.nhc.gov.cn/",
            version="2023",
        ),
        RuleSource(
            title="Adult Obesity Dietary Guidance",
            url="https://www.nhc.gov.cn/",
            version="2024",
        ),
    )
    rules = {
        concepts.require(CodeKind.CONDITION, "hypertension"): ConditionRule(
            condition=concepts.require(CodeKind.CONDITION, "hypertension"),
            hard_exclusions={concepts.require(CodeKind.CONTRAINDICATION, "high_sodium")},
            preferred_tags={
                concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"),
                concepts.require(CodeKind.NUTRITION_TAG, "vegetable_rich"),
            },
            nutrition_limits={
                NutrientLimit(
                    metric=NutrientMetric.SODIUM_MG,
                    scope=LimitScope.PER_MEAL,
                    max_value=700,
                ),
            },
        ),
        concepts.require(CodeKind.CONDITION, "diabetes"): ConditionRule(
            condition=concepts.require(CodeKind.CONDITION, "diabetes"),
            hard_exclusions={
                concepts.require(CodeKind.CONTRAINDICATION, "sugary_drink"),
                concepts.require(CodeKind.CONTRAINDICATION, "dessert"),
            },
            preferred_tags={
                concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"),
                concepts.require(CodeKind.NUTRITION_TAG, "high_fiber"),
            },
            nutrition_limits={
                NutrientLimit(
                    metric=NutrientMetric.SUGAR_G,
                    scope=LimitScope.DAILY,
                    max_value=25,
                ),
                NutrientLimit(
                    metric=NutrientMetric.SUGAR_G,
                    scope=LimitScope.ROLLING_WINDOW,
                    max_value=15,
                    window_hours=4,
                ),
            },
        ),
        concepts.require(CodeKind.CONDITION, "hyperlipidemia"): ConditionRule(
            condition=concepts.require(CodeKind.CONDITION, "hyperlipidemia"),
            hard_exclusions={
                concepts.require(CodeKind.CONTRAINDICATION, "deep_fried"),
                concepts.require(CodeKind.CONTRAINDICATION, "fatty_meat"),
            },
            preferred_tags={
                concepts.require(CodeKind.NUTRITION_TAG, "lean_protein"),
                concepts.require(CodeKind.NUTRITION_TAG, "vegetable_rich"),
            },
            nutrition_limits={
                NutrientLimit(
                    metric=NutrientMetric.FAT_G,
                    scope=LimitScope.PER_MEAL,
                    max_value=25,
                ),
            },
        ),
        concepts.require(CodeKind.CONDITION, "weight_control"): ConditionRule(
            condition=concepts.require(CodeKind.CONDITION, "weight_control"),
            hard_exclusions={concepts.require(CodeKind.CONTRAINDICATION, "oversized_portion")},
            preferred_tags={
                concepts.require(CodeKind.NUTRITION_TAG, "balanced"),
                concepts.require(CodeKind.NUTRITION_TAG, "high_fiber"),
                concepts.require(CodeKind.NUTRITION_TAG, "lean_protein"),
            },
            nutrition_limits={
                NutrientLimit(
                    metric=NutrientMetric.ENERGY_KCAL,
                    scope=LimitScope.PER_MEAL,
                    max_value=650,
                ),
            },
        ),
    }
    return RulePack(
        version="baseline-2026-05-15",
        sources=sources,
        concepts=concepts,
        rules_by_condition=rules,
    )


def _baseline_concepts() -> ConceptRegistry:
    definitions = [
        ConceptDefinition(ConceptCode(CodeKind.CONDITION, "hypertension"), "Hypertension", aliases=("hypertension",)),
        ConceptDefinition(ConceptCode(CodeKind.CONDITION, "diabetes"), "Diabetes", aliases=("diabetes",)),
        ConceptDefinition(ConceptCode(CodeKind.CONDITION, "hyperlipidemia"), "Hyperlipidemia", aliases=("hyperlipidemia",)),
        ConceptDefinition(ConceptCode(CodeKind.CONDITION, "weight_control"), "Weight control", aliases=("weight control",)),
        ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium"), "High sodium"),
        ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "sugary_drink"), "Sugary drink"),
        ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "dessert"), "Dessert"),
        ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "deep_fried"), "Deep fried"),
        ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "fatty_meat"), "Fatty meat"),
        ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "oversized_portion"), "Oversized portion"),
        ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium"), "Low sodium"),
        ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "vegetable_rich"), "Vegetable rich"),
        ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "controlled_carbs"), "Controlled carbohydrates"),
        ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "high_fiber"), "High fiber"),
        ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "lean_protein"), "Lean protein"),
        ConceptDefinition(ConceptCode(CodeKind.NUTRITION_TAG, "balanced"), "Balanced"),
    ]
    return ConceptRegistry(definitions)


def _require_code_set(field_name: str, values: set[ConceptCode], expected_kind: CodeKind) -> None:
    for value in values:
        _require_code_kind(field_name, value, expected_kind)


def _require_code_kind(field_name: str, value: ConceptCode, expected_kind: CodeKind) -> None:
    if not isinstance(value, ConceptCode):
        raise TypeError(f"{field_name} must be a ConceptCode")
    if value.kind != expected_kind:
        raise TypeError(f"{field_name} must use {expected_kind.value} codes")
