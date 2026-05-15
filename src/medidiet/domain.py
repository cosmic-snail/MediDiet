from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite


class CodeKind(str, Enum):
    CONDITION = "condition"
    ALLERGEN = "allergen"
    CONTRAINDICATION = "contraindication"
    NUTRITION_TAG = "nutrition_tag"
    TASTE_TAG = "taste_tag"
    INGREDIENT = "ingredient"


class DataSource(str, Enum):
    PATIENT_REPORTED = "patient_reported"
    CLINICIAN_ENTERED = "clinician_entered"
    HIS_EMR = "his_emr"
    MERCHANT_LABEL = "merchant_label"
    HUMAN_CURATED = "human_curated"
    SYSTEM_ESTIMATED = "system_estimated"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Outcome(str, Enum):
    RECOMMENDED = "recommended"
    DOWNGRADED = "downgraded"
    REFUSED = "refused"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


@dataclass(frozen=True)
class ConceptCode:
    kind: CodeKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CodeKind):
            raise TypeError("kind must be a CodeKind")
        if not isinstance(self.value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?", self.value):
            raise ValueError("concept code value must be normalized snake_case")


@dataclass(frozen=True)
class ConceptDefinition:
    code: ConceptCode
    display_name: str
    aliases: tuple[str, ...] = ()
    source: str = "baseline"


class ConceptRegistry:
    def __init__(self, definitions: list[ConceptDefinition]):
        self._definitions = {(definition.code.kind, definition.code.value): definition for definition in definitions}
        self._aliases: dict[tuple[CodeKind, str], ConceptCode] = {}
        for definition in definitions:
            for alias in definition.aliases:
                self._aliases[(definition.code.kind, alias.strip().lower())] = definition.code

    def require(self, kind: CodeKind, value: str) -> ConceptCode:
        code = ConceptCode(kind, value)
        if (code.kind, code.value) not in self._definitions:
            raise ValueError(f"unknown concept code: {kind.value}:{value}")
        return code

    def resolve_alias(self, kind: CodeKind, alias: str) -> ConceptCode:
        normalized = alias.strip().lower()
        if (kind, normalized) not in self._aliases:
            raise ValueError(f"unknown alias for {kind.value}: {alias}")
        return self._aliases[(kind, normalized)]


@dataclass(frozen=True)
class Confidence:
    value: float

    def __post_init__(self) -> None:
        if not isinstance(self.value, int | float) or not isfinite(self.value) or self.value < 0 or self.value > 1:
            raise ValueError("confidence must be between 0 and 1")

    def is_low(self, threshold: float = 0.7) -> bool:
        return self.value < threshold


@dataclass
class Nutrients:
    energy_kcal: float = 0
    carbs_g: float = 0
    protein_g: float = 0
    fat_g: float = 0
    sodium_mg: float = 0
    sugar_g: float = 0
    fiber_g: float = 0

    def __post_init__(self) -> None:
        for field_name, value in self.__dict__.items():
            _validate_non_negative_number(field_name, value, maximum=1_000_000)

    def __iadd__(self, other: "Nutrients") -> "Nutrients":
        self.energy_kcal += other.energy_kcal
        self.carbs_g += other.carbs_g
        self.protein_g += other.protein_g
        self.fat_g += other.fat_g
        self.sodium_mg += other.sodium_mg
        self.sugar_g += other.sugar_g
        self.fiber_g += other.fiber_g
        return self


@dataclass(frozen=True)
class Preference:
    disliked_ingredients: set[ConceptCode] = field(default_factory=set)
    taste_tags: set[ConceptCode] = field(default_factory=set)
    max_price_cents: int | None = None
    max_distance_meters: int | None = None

    def __post_init__(self) -> None:
        _validate_code_set("disliked_ingredients", self.disliked_ingredients, CodeKind.INGREDIENT)
        _validate_code_set("taste_tags", self.taste_tags, CodeKind.TASTE_TAG)
        if self.max_price_cents is not None:
            _validate_non_negative_int("max_price_cents", self.max_price_cents)
        if self.max_distance_meters is not None:
            _validate_non_negative_int("max_distance_meters", self.max_distance_meters)


@dataclass(frozen=True)
class PatientProfile:
    patient_id: str
    age: int
    height_cm: float
    weight_kg: float
    conditions: set[ConceptCode]
    allergens: set[ConceptCode]
    contraindications: set[ConceptCode]
    preferences: Preference
    key_risk_fields_confirmed: bool
    source: DataSource

    def __post_init__(self) -> None:
        if not isinstance(self.age, int) or self.age < 0 or self.age > 130:
            raise ValueError("age must be an integer between 0 and 130")
        _validate_non_negative_number("height_cm", self.height_cm, minimum_exclusive=True, maximum=260)
        _validate_non_negative_number("weight_kg", self.weight_kg, minimum_exclusive=True, maximum=600)
        _validate_code_set("conditions", self.conditions, CodeKind.CONDITION)
        _validate_code_set("allergens", self.allergens, CodeKind.ALLERGEN)
        _validate_code_set("contraindications", self.contraindications, CodeKind.CONTRAINDICATION)
        if not isinstance(self.source, DataSource):
            raise TypeError("source must be a DataSource")

    @property
    def bmi(self) -> float:
        meters = self.height_cm / 100
        return round(self.weight_kg / (meters * meters), 1)

    def is_adult(self) -> bool:
        return self.age >= 18


@dataclass(frozen=True)
class IntakeRecord:
    food_label: str
    meal_time: str
    portion: str
    nutrients: Nutrients
    confidence: Confidence
    source: DataSource
    manually_corrected: bool = False


@dataclass(frozen=True)
class MenuItem:
    item_id: str
    merchant_id: str
    name: str
    ingredients: set[ConceptCode]
    allergens: set[ConceptCode]
    taste_tags: set[ConceptCode]
    nutrients: Nutrients
    nutrition_confidence: Confidence
    source: DataSource
    price_cents: int
    distance_meters: int
    merchant_reliability: float
    available: bool = True

    def __post_init__(self) -> None:
        _validate_code_set("ingredients", self.ingredients, CodeKind.INGREDIENT)
        _validate_code_set("allergens", self.allergens, CodeKind.ALLERGEN)
        _validate_code_set("taste_tags", self.taste_tags, CodeKind.TASTE_TAG)
        _validate_non_negative_int("price_cents", self.price_cents)
        _validate_non_negative_int("distance_meters", self.distance_meters)
        if not isinstance(self.merchant_reliability, int | float) or not isfinite(self.merchant_reliability) or not 0 <= self.merchant_reliability <= 1:
            raise ValueError("merchant_reliability must be between 0 and 1")

    def contains_allergen(self, allergen: ConceptCode) -> bool:
        if allergen.kind != CodeKind.ALLERGEN:
            raise TypeError("allergen must have kind ALLERGEN")
        return allergen in self.allergens


def _validate_code_set(field_name: str, values: set[ConceptCode], expected_kind: CodeKind) -> None:
    for value in values:
        if not isinstance(value, ConceptCode):
            raise TypeError(f"{field_name} must contain ConceptCode values")
        if value.kind != expected_kind:
            raise TypeError(f"{field_name} must contain {expected_kind.value} codes")


def _validate_non_negative_number(
    field_name: str,
    value: float,
    minimum_exclusive: bool = False,
    maximum: float | None = None,
) -> None:
    if not isinstance(value, int | float) or not isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    if minimum_exclusive and value <= 0:
        raise ValueError(f"{field_name} must be greater than 0")
    if not minimum_exclusive and value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field_name} is unrealistically large")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
