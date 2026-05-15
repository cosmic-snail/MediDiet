from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from medidiet.domain import CodeKind, ConceptCode, MealLabel
from medidiet.nutrition import NextMealTarget, RemainingNutrientLimit
from medidiet.rules import LimitScope, NutrientMetric, RulePack


class MealInstruction(IntEnum):
    AVOID_EXTRA_SAUCE = 4001
    CONTROL_ADDED_SUGAR = 4002
    AVOID_DEEP_FRIED = 4003
    CONTROL_PORTION_SIZE = 4004


@dataclass(frozen=True)
class MealPlan:
    meal_label: MealLabel
    required_tags: frozenset[ConceptCode] = field(default_factory=frozenset)
    avoid_tags: frozenset[ConceptCode] = field(default_factory=frozenset)
    instructions: tuple[MealInstruction, ...] = field(default_factory=tuple)
    limits: tuple[RemainingNutrientLimit, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.meal_label, MealLabel):
            raise TypeError("meal_label must be a MealLabel")
        _require_code_kind_set("required_tags", self.required_tags, CodeKind.NUTRITION_TAG)
        _require_code_kind_set("avoid_tags", self.avoid_tags, CodeKind.CONTRAINDICATION)
        for instruction in self.instructions:
            if not isinstance(instruction, MealInstruction):
                raise TypeError("instructions must contain MealInstruction values")


class MealPlanGenerator:
    def __init__(self, rule_pack: RulePack):
        self.rule_pack = rule_pack

    def generate(self, target: NextMealTarget, meal_label: MealLabel) -> MealPlan:
        if not isinstance(meal_label, MealLabel):
            raise TypeError("meal_label must be a MealLabel")

        required_tags = set(target.preferred_tags)
        avoid_tags: set[ConceptCode] = set()
        instructions: set[MealInstruction] = set()

        for limit in target.limits:
            if limit.metric is NutrientMetric.SODIUM_MG and limit.scope is LimitScope.PER_MEAL:
                required_tags.add(self.rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"))
                avoid_tags.add(self.rule_pack.concepts.require(CodeKind.CONTRAINDICATION, "high_sodium"))
                instructions.add(MealInstruction.AVOID_EXTRA_SAUCE)
            if limit.metric is NutrientMetric.SUGAR_G:
                required_tags.add(self.rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"))
                avoid_tags.add(self.rule_pack.concepts.require(CodeKind.CONTRAINDICATION, "sugary_drink"))
                instructions.add(MealInstruction.CONTROL_ADDED_SUGAR)
            if limit.metric is NutrientMetric.FAT_G:
                required_tags.add(self.rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "lean_protein"))
                avoid_tags.add(self.rule_pack.concepts.require(CodeKind.CONTRAINDICATION, "deep_fried"))
                instructions.add(MealInstruction.AVOID_DEEP_FRIED)
            if limit.metric is NutrientMetric.ENERGY_KCAL:
                required_tags.add(self.rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "balanced"))
                avoid_tags.add(self.rule_pack.concepts.require(CodeKind.CONTRAINDICATION, "oversized_portion"))
                instructions.add(MealInstruction.CONTROL_PORTION_SIZE)

        return MealPlan(
            meal_label=meal_label,
            required_tags=frozenset(required_tags),
            avoid_tags=frozenset(avoid_tags),
            instructions=tuple(sorted(instructions, key=lambda instruction: instruction.value)),
            limits=target.limits,
        )


def _require_code_kind_set(field_name: str, values: frozenset[ConceptCode], expected_kind: CodeKind) -> None:
    for value in values:
        if not isinstance(value, ConceptCode):
            raise TypeError(f"{field_name} must contain ConceptCode values")
        if value.kind is not expected_kind:
            raise TypeError(f"{field_name} must contain {expected_kind.value} codes")
