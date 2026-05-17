# Recommendation Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a testable MediDiet recommendation-engine core that can safety-gate adult chronic-disease meal recommendations, produce next-meal plans, match concrete menu items, explain outcomes, and expose extension contracts for later mini-program, photo-recognition, delivery-platform, HIS/EMR, LLM, rule-pack, review-console, and audit integrations.

**Architecture:** Implement a rules-first Python package under `src/medidiet`. The core remains dependency-light and deterministic: domain models, rule packs, safety gate, nutrition state calculator, meal-plan generator, menu matcher, explanation builder, trace writer, orchestration engine, and extension-port contracts are separate files with clear responsibilities. External systems are represented as typed ports/adapters; they provide evidence to the engine and cannot bypass safety gates.

**Tech Stack:** Python 3.11+ standard library, `dataclasses`, `enum`, `typing.Protocol`, `unittest`, `json`, optional local CLI via `python -m medidiet.cli`.

---

## Scope Check

This plan implements Phase 1 from the approved design: recommendation-engine core, rule baseline, simulated intake/menu data, filtering, scoring, explanation, audit trace, and extension-port contracts. It intentionally does not implement the mini-program UI, real photo-recognition model, real delivery checkout, real HIS/EMR integration, or production clinical thresholds. Those are future plans that will consume the interfaces created here.

## File Structure

- `pyproject.toml` - Package metadata and Python version.
- `src/medidiet/__init__.py` - Public package exports.
- `src/medidiet/domain.py` - Enums and dataclasses used across the engine.
- `src/medidiet/rules.py` - Versioned baseline rule pack and rule lookup helpers.
- `src/medidiet/safety.py` - Eligibility, allergy, contraindication, data-confidence, and hard-rule checks.
- `src/medidiet/nutrition.py` - Daily nutrition aggregation and next-meal target calculation.
- `src/medidiet/planner.py` - Meal-plan generation before concrete menu matching.
- `src/medidiet/matcher.py` - Menu hard filtering and weighted ranking.
- `src/medidiet/explainer.py` - Patient and clinician explanation construction from rule hits and scores.
- `src/medidiet/trace.py` - Recommendation trace creation and JSON serialization.
- `src/medidiet/engine.py` - Recommendation orchestration and outcome policy.
- `src/medidiet/ports.py` - Extension interfaces, adapter DTOs, and event names.
- `src/medidiet/fixtures.py` - Deterministic sample patients, intake records, menus, and rules for tests and CLI.
- `src/medidiet/cli.py` - Local demo runner for manual verification.
- `tests/test_domain.py` - Domain model behavior.
- `tests/test_rules.py` - Rule pack and source governance behavior.
- `tests/test_safety.py` - Safety gate behavior.
- `tests/test_nutrition.py` - Daily intake and next-meal target behavior.
- `tests/test_planner.py` - Meal-plan generation behavior.
- `tests/test_matcher.py` - Hard exclusion and ranking behavior.
- `tests/test_explainer_trace.py` - Explanation and trace behavior.
- `tests/test_engine.py` - End-to-end orchestration behavior.
- `tests/test_ports.py` - Extension contract behavior.

## Commands Used Throughout

- Run all tests: `PYTHONPATH=src python -m unittest discover -s tests -v`
- Run one test module: `PYTHONPATH=src python -m unittest tests.test_engine -v`
- Run demo CLI: `PYTHONPATH=src python -m medidiet.cli`

---

### Task 1: Project Scaffold and Smoke Test

**Files:**
- Create: `pyproject.toml`
- Create: `src/medidiet/__init__.py`
- Create: `tests/test_domain.py`

- [ ] **Step 1: Create a failing smoke test**

Create `tests/test_domain.py`:

```python
import unittest


class DomainSmokeTest(unittest.TestCase):
    def test_package_imports(self):
        import medidiet

        self.assertEqual(medidiet.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the smoke test and verify it fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet'`.

- [ ] **Step 3: Add package scaffold**

Create `pyproject.toml`:

```toml
[project]
name = "medidiet"
version = "0.1.0"
description = "Hospital diet agent recommendation engine core"
requires-python = ">=3.11"

[tool.setuptools.packages.find]
where = ["src"]
```

Create `src/medidiet/__init__.py`:

```python
"""MediDiet recommendation engine core."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Run the smoke test and verify it passes**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

Expected: PASS with `test_package_imports`.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml src/medidiet/__init__.py tests/test_domain.py
git commit -m "feat: scaffold recommendation engine package"
```

---

### Task 2: Domain Models

**Files:**
- Create: `src/medidiet/domain.py`
- Modify: `tests/test_domain.py`

- [ ] **Step 1: Extend domain tests with a table-driven concept registry**

Replace `tests/test_domain.py` with:

```python
import unittest

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    ConceptDefinition,
    ConceptRegistry,
    Confidence,
    DataSource,
    MenuItem,
    Nutrients,
    Outcome,
    PatientProfile,
    Preference,
)


class DomainSmokeTest(unittest.TestCase):
    def test_package_imports(self):
        import medidiet

        self.assertEqual(medidiet.__version__, "0.1.0")


class DomainModelTest(unittest.TestCase):
    def setUp(self):
        self.registry = ConceptRegistry(
            [
                ConceptDefinition(ConceptCode(CodeKind.CONDITION, "hypertension"), "高血压", aliases=("高血压", "hypertension")),
                ConceptDefinition(ConceptCode(CodeKind.ALLERGEN, "peanut"), "花生", aliases=("花生", "peanut")),
                ConceptDefinition(ConceptCode(CodeKind.ALLERGEN, "shrimp"), "虾", aliases=("虾", "shrimp")),
                ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium"), "高钠禁忌"),
                ConceptDefinition(ConceptCode(CodeKind.TASTE_TAG, "light"), "清淡"),
                ConceptDefinition(ConceptCode(CodeKind.INGREDIENT, "chicken"), "鸡肉"),
            ]
        )

    def test_registry_returns_registered_concept_codes(self):
        code = self.registry.require(CodeKind.CONDITION, "hypertension")

        self.assertEqual(code.kind, CodeKind.CONDITION)
        self.assertEqual(code.value, "hypertension")
        self.assertEqual(self.registry.resolve_alias(CodeKind.ALLERGEN, "花生").value, "peanut")

    def test_registry_rejects_unknown_or_malformed_codes(self):
        with self.assertRaises(ValueError):
            self.registry.require(CodeKind.CONDITION, "kidney_disease")
        with self.assertRaises(ValueError):
            ConceptCode(CodeKind.CONDITION, "")
        with self.assertRaises(ValueError):
            ConceptCode(CodeKind.CONDITION, "High Sodium")
        with self.assertRaises(ValueError):
            ConceptCode(CodeKind.CONDITION, " high_sodium")

    def test_patient_profile_uses_concept_codes_for_medical_constraints(self):
        hypertension = self.registry.require(CodeKind.CONDITION, "hypertension")
        peanut = self.registry.require(CodeKind.ALLERGEN, "peanut")
        high_sodium = self.registry.require(CodeKind.CONTRAINDICATION, "high_sodium")
        light = self.registry.require(CodeKind.TASTE_TAG, "light")

        profile = PatientProfile(
            patient_id="p-1",
            age=45,
            height_cm=170.5,
            weight_kg=80.2,
            conditions={hypertension},
            allergens={peanut},
            contraindications={high_sodium},
            preferences=Preference(taste_tags={light}),
            key_risk_fields_confirmed=False,
            source=DataSource.PATIENT_REPORTED,
        )

        self.assertFalse(profile.key_risk_fields_confirmed)
        self.assertIn(hypertension, profile.conditions)
        self.assertIn(peanut, profile.allergens)
        self.assertIn(high_sodium, profile.contraindications)
        self.assertIn(light, profile.preferences.taste_tags)

    def test_patient_profile_rejects_wrong_code_kinds(self):
        peanut = self.registry.require(CodeKind.ALLERGEN, "peanut")
        hypertension = self.registry.require(CodeKind.CONDITION, "hypertension")

        with self.assertRaises(TypeError):
            PatientProfile(
                patient_id="p-1",
                age=45,
                height_cm=170,
                weight_kg=80,
                conditions={peanut},
                allergens=set(),
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )
        with self.assertRaises(TypeError):
            PatientProfile(
                patient_id="p-1",
                age=45,
                height_cm=170,
                weight_kg=80,
                conditions={hypertension},
                allergens={hypertension},
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )

    def test_patient_profile_rejects_invalid_numeric_boundaries(self):
        hypertension = self.registry.require(CodeKind.CONDITION, "hypertension")

        for field, value in [("age", -1), ("age", 200), ("height_cm", 0), ("weight_kg", -10)]:
            payload = dict(
                patient_id="p-1",
                age=45,
                height_cm=170,
                weight_kg=80,
                conditions={hypertension},
                allergens=set(),
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )
            payload[field] = value
            with self.assertRaises(ValueError):
                PatientProfile(**payload)

    def test_nutrients_accept_float_values_and_add(self):
        total = Nutrients(energy_kcal=100.5, carbs_g=10.25, protein_g=5.5, fat_g=2, sodium_mg=300.5, sugar_g=1, fiber_g=2)
        total += Nutrients(energy_kcal=50.25, carbs_g=5.25, protein_g=3, fat_g=1, sodium_mg=100.25, sugar_g=2, fiber_g=1)

        self.assertAlmostEqual(total.energy_kcal, 150.75)
        self.assertAlmostEqual(total.carbs_g, 15.5)
        self.assertAlmostEqual(total.sodium_mg, 400.75)
        self.assertEqual(total.sugar_g, 3)

    def test_nutrients_reject_negative_non_finite_and_absurd_values(self):
        for kwargs in [
            {"sodium_mg": -1},
            {"energy_kcal": float("inf")},
            {"sodium_mg": 1_000_001},
        ]:
            with self.assertRaises(ValueError):
                Nutrients(**kwargs)

    def test_menu_item_allergen_matching_uses_code_sets(self):
        peanut = self.registry.require(CodeKind.ALLERGEN, "peanut")
        shrimp = self.registry.require(CodeKind.ALLERGEN, "shrimp")
        light = self.registry.require(CodeKind.TASTE_TAG, "light")
        chicken = self.registry.require(CodeKind.INGREDIENT, "chicken")

        item = MenuItem(
            item_id="m-1",
            merchant_id="shop-1",
            name="Peanut Chicken Bowl",
            ingredients={chicken},
            allergens={peanut},
            taste_tags={light},
            nutrients=Nutrients(energy_kcal=560, carbs_g=55, protein_g=32, fat_g=22, sodium_mg=900, sugar_g=8, fiber_g=4),
            nutrition_confidence=Confidence(0.9),
            source=DataSource.MERCHANT_LABEL,
            price_cents=3200,
            distance_meters=900,
            merchant_reliability=0.8,
        )

        self.assertTrue(item.contains_allergen(peanut))
        self.assertFalse(item.contains_allergen(shrimp))
        self.assertEqual(Outcome.RECOMMENDED.value, "recommended")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the domain tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.domain'`.

- [ ] **Step 3: Implement domain models**

Create `src/medidiet/domain.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
import re


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


def _validate_non_negative_number(field_name: str, value: float, minimum_exclusive: bool = False, maximum: float | None = None) -> None:
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
```

- [ ] **Step 4: Run the domain tests and verify they pass**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_domain -v
```

Expected: PASS with eight tests.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/domain.py tests/test_domain.py
git commit -m "feat: add recommendation domain models"
```

---

### Task 3: Versioned Baseline Rule Pack

**Files:**
- Create: `src/medidiet/rules.py`
- Create: `tests/test_rules.py`

- [ ] **Step 1: Write failing rule tests**

Create `tests/test_rules.py`:

```python
import unittest

from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import (
    ConditionRule,
    LimitScope,
    NutrientLimit,
    NutrientMetric,
    load_baseline_rule_pack,
)


class RulePackTest(unittest.TestCase):
    def test_rule_pack_has_version_sources_and_registry(self):
        pack = load_baseline_rule_pack()

        self.assertEqual(pack.version, "baseline-2026-05-15")
        self.assertGreaterEqual(len(pack.sources), 4)
        self.assertEqual(pack.concepts.require(CodeKind.CONDITION, "hypertension").value, "hypertension")
        self.assertEqual(pack.concepts.require(CodeKind.CONDITION, "diabetes").value, "diabetes")

    # Full Task 3 tests cover ConceptCode-backed rule lookup, hypertension
    # per-meal sodium limits, diabetes daily and rolling-window sugar limits,
    # invalid nutrient limit boundaries, and wrong ConceptCode kinds.


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_rules -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.rules'`.

- [ ] **Step 3: Implement the baseline rule pack**

Create `src/medidiet/rules.py`:

```python
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
        # ROLLING_WINDOW requires positive window_hours; DAILY/PER_MEAL forbid it.
        ...


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


@dataclass(frozen=True)
class RulePack:
    version: str
    sources: tuple[RuleSource, ...]
    concepts: ConceptRegistry
    rules_by_condition: dict[ConceptCode, ConditionRule]

    def for_condition(self, condition: ConceptCode) -> ConditionRule:
        return self.rules_by_condition[condition]


def load_baseline_rule_pack() -> RulePack:
    # Build baseline ConceptRegistry and ConditionRule table.
    # Diabetes uses both DAILY and ROLLING_WINDOW sugar limits.
    ...
```

- [ ] **Step 4: Run rule tests and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_rules -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS for `test_rules` and full suite.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/rules.py tests/test_rules.py
git commit -m "feat: add versioned baseline rule pack"
```

---

### Task 4: Safety Gate

**Files:**
- Create: `src/medidiet/safety.py`
- Create: `tests/test_safety.py`

- [ ] **Step 1: Write failing safety tests**

Create `tests/test_safety.py`, using the current file as source of truth. Cover:

- Returned safety events use `SafetyCode(IntEnum)` integer codes, not strings or floats.
- Allergy matches create hard-block events and warning logs.
- Unconfirmed patient risk fields create uncertainty events and warning logs.
- Low-confidence intake records create uncertainty events and warning logs.
- Per-meal nutrient limits create hard-block events and warning logs.
- Safe candidate loops emit no below-warning logs.
- Safety logs include timestamp, process id, thread id, integer code, code name, event severity, and rule-pack version.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_safety -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.safety'`.

- [ ] **Step 3: Implement safety gate**

Create `src/medidiet/safety.py`, using the current file as source of truth. Implement:

- `SafetyCode(IntEnum)`.
- `SafetySeverity(IntEnum)`.
- `SafetyEvent`.
- `SafetyResult`.
- `SafetyGate.evaluate(...)`.
- Warning-level file logging for each hard block or uncertainty.

Logging must follow `docs/superpowers/specs/2026-05-15-safety-logging-principles.md`.

- [ ] **Step 4: Run safety and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_safety -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/safety.py tests/test_safety.py
git commit -m "feat: add recommendation safety gate"
```

---

### Task 5: Nutrition State and Next-Meal Target

**Files:**
- Update: `src/medidiet/domain.py`
- Create: `src/medidiet/nutrition.py`
- Create: `tests/test_nutrition.py`

- [ ] **Step 1: Write failing nutrition tests**

Create `tests/test_nutrition.py`, using the current file as source of truth. Cover:

- Daily intake totals aggregate float nutrient values.
- Low-confidence records are reported but still counted in totals.
- Next-meal preferred tags are `ConceptCode(NUTRITION_TAG, ...)`, not strings.
- `DAILY` sugar limits calculate remaining allowance from same-day intake.
- `ROLLING_WINDOW` sugar limits count only records inside the configured window.
- `PER_MEAL` limits carry forward without subtracting daily intake.
- `IntakeRecord` uses timezone-aware `occurred_at` plus `meal_label` rather than a free-text meal time.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_nutrition -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.nutrition'`.

- [ ] **Step 3: Implement nutrition calculation**

Update `IntakeRecord` in `src/medidiet/domain.py` to store `occurred_at: datetime` and `meal_label: str`, requiring a timezone-aware timestamp.

Create `src/medidiet/nutrition.py`, using the current file as source of truth. Implement:

- `NutritionReason(IntEnum)`.
- `DailyNutritionState`.
- `RemainingNutrientLimit`.
- `NextMealTarget`.
- `DailyNutritionCalculator.aggregate(...)`.
- `DailyNutritionCalculator.next_meal_target(...)`.

The calculator should consume `RulePack` table-driven `NutrientLimit` entries and return structured remaining limits rather than scattered `max_*` fields.

- [ ] **Step 4: Run nutrition and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_nutrition -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/nutrition.py tests/test_nutrition.py
git commit -m "feat: calculate daily nutrition targets"
```

---

### Task 6: Meal Plan Generator

**Files:**
- Update: `src/medidiet/domain.py`
- Create: `src/medidiet/planner.py`
- Create: `tests/test_planner.py`

- [ ] **Step 1: Write failing planner tests**

Create `tests/test_planner.py`, using the current file as source of truth. Cover:

- `MealPlanGenerator` consumes structured `NextMealTarget`.
- `MealPlan.meal_label` uses `MealLabel(IntEnum)`, not free-text strings.
- `required_tags` and `avoid_tags` are `ConceptCode` sets, not strings.
- Per-meal sodium limits add `low_sodium`, avoid `high_sodium`, and add `MealInstruction.AVOID_EXTRA_SAUCE`.
- Daily or rolling sugar limits add `controlled_carbs`, avoid `sugary_drink`, and add `MealInstruction.CONTROL_ADDED_SUGAR`.
- `MealInstruction` uses integer enum values.
- `MealPlan` preserves structured nutrient limits for downstream menu matching.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_planner -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.planner'`.

- [ ] **Step 3: Implement planner**

Update `src/medidiet/domain.py` with `MealLabel(IntEnum)` and require it in `IntakeRecord`.

Create `src/medidiet/planner.py`, using the current file as source of truth. Implement:

- `MealInstruction(IntEnum)`.
- `MealPlan`.
- `MealPlanGenerator.generate(...)`.

The generator should derive plan tags and instructions from structured `RemainingNutrientLimit` values and use `RulePack.concepts` for all tags.

- [ ] **Step 4: Run planner and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_planner -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/planner.py tests/test_planner.py
git commit -m "feat: generate nutrition meal plans"
```

---

### Task 7: Menu Matcher

**Files:**
- Update: `src/medidiet/domain.py`
- Create: `src/medidiet/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: Write failing matcher tests**

Create `tests/test_matcher.py`, using the current file as source of truth. Cover:

- `MenuMatcher.match(...)` returns structured accepted and excluded results.
- Avoid-tag hits exclude candidates with `MatchRejectionCode.AVOID_TAG`.
- Per-meal nutrient limit violations exclude candidates with `MatchRejectionCode.NUTRIENT_LIMIT_EXCEEDED`.
- Unavailable candidates exclude with `MatchRejectionCode.UNAVAILABLE`.
- Rejection codes use `IntEnum` integer values, not strings or floats.
- Accepted candidates are sorted by score descending.
- Scoring considers required nutrition tags, patient taste preferences, price, distance, and merchant reliability.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_matcher -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.matcher'`.

- [ ] **Step 3: Implement matcher**

Update `src/medidiet/domain.py` so `MenuItem` can carry:

- `nutrition_tags: set[ConceptCode]`
- `contraindication_tags: set[ConceptCode]`

Create `src/medidiet/matcher.py`, using the current file as source of truth. Implement:

- `MatchRejectionCode(IntEnum)`.
- `MatchRejection`.
- `MenuItemScore`.
- `MatchResult`.
- `MenuMatcher.match(...)`.

The matcher should use `MenuItem.nutrition_tags` for required-tag scoring, `MenuItem.contraindication_tags` for avoid-tag filtering, and structured `MealPlan.limits` for per-meal nutrient filtering.

- [ ] **Step 4: Run matcher and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_matcher -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/matcher.py tests/test_matcher.py
git commit -m "feat: match and rank safe menu items"
```

---

### Task 8: Explanation and Trace

**Files:**
- Create: `src/medidiet/explainer.py`
- Create: `src/medidiet/trace.py`
- Create: `tests/test_explainer_trace.py`

- [ ] **Step 1: Write failing explanation and trace tests**

Create `tests/test_explainer_trace.py`, using the current file as source of truth. Cover:

- Patient explanations are deterministic Chinese text generated from `ConceptCode` tags and `MealInstruction` values.
- Patient explanations do not include medication adjustment, diagnosis, or treatment advice.
- Clinician explanations are structured dictionaries with integer safety and rejection codes.
- Clinician explanations include rule version, safety events, exclusions, scores, matched tags, and an `llmBoundary`.
- `RecommendationTrace.to_json()` serializes stable camelCase fields, including `traceId`, `patientId`, `ruleVersion`, `outcome`, `riskLevel`, `createdAt`, `safetyEvents`, and `exclusions`.
- Trace safety events and exclusions store integer codes, not string reasons.
- Trace does not accept sensitive fields such as patient name, phone number, or photo URI.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_explainer_trace -v
```

Expected: FAIL with `ModuleNotFoundError` for `medidiet.explainer` or `medidiet.trace`.

- [ ] **Step 3: Implement explanation builder and trace**

Create `src/medidiet/explainer.py` and `src/medidiet/trace.py`, using the current files as source of truth. Implement:

- `ExplanationBuilder.patient_explanation(...)`.
- `ExplanationBuilder.clinician_explanation(...)`.
- Structured conversion helpers for `SafetyEvent`, `MatchRejection`, and `ConceptCode`.
- `RecommendationTrace.to_dict()`.
- `RecommendationTrace.to_json()`.

The implementation must keep patient-facing language deterministic and must serialize trace context without sensitive patient identity fields.

- [ ] **Step 4: Run explanation/trace and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_explainer_trace -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/explainer.py src/medidiet/trace.py tests/test_explainer_trace.py
git commit -m "feat: explain and trace recommendations"
```

---

### Task 9: Engine Orchestration

**Files:**
- Create: `src/medidiet/engine.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write failing engine tests**

Create `tests/test_engine.py`, using the current file as source of truth. Cover:

- Successful recommendation orchestrates safety, nutrition, planning, matching, explanation, and trace.
- Returned recommendation uses `Outcome.RECOMMENDED`, picks the highest-ranked accepted item, and records scores in trace.
- Refusal path uses matcher exclusions, returns `Outcome.REFUSED`, no recommended items, and stores `MatchRejectionCode` integer codes in trace.
- Human-review path uses safety events, returns `Outcome.HUMAN_REVIEW_REQUIRED`, no recommended items, and stores `SafetyCode` integer codes in trace.
- `RecommendationEngine.recommend(...)` requires `MealLabel`, not a free-text meal label string.
- Test fixtures use `ConceptCode` conditions, allergens, nutrition tags, taste tags, and structured `IntakeRecord.occurred_at`.

- [ ] **Step 2: Run engine tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_engine -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.engine'`.

- [ ] **Step 3: Implement engine orchestration**

Create `src/medidiet/engine.py`, using the current file as source of truth. Implement:

- `RecommendationResult`.
- `RecommendationEngine.__init__(...)`.
- `RecommendationEngine.recommend(...)`.
- `RecommendationEngine._finalize(...)`.

The engine should run safety first; route hard blocks or uncertainty to human review; otherwise calculate the next-meal target, generate a meal plan, match menu items, refuse if no candidate survives, and build deterministic explanations and trace payloads with integer codes.

- [ ] **Step 4: Run engine and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_engine -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/engine.py tests/test_engine.py
git commit -m "feat: orchestrate recommendation engine"
```

---

### Task 10: Extension Ports and Events

**Files:**
- Create: `src/medidiet/ports.py`
- Create: `tests/test_ports.py`

- [ ] **Step 1: Write failing port tests**

Create `tests/test_ports.py`, using the current file as source of truth. Cover:

- `RecommendationRequestEnvelope` carries schema version, source system, source version, request id, and timezone-aware `created_at`.
- Envelope serialization emits stable camelCase including `createdAt`.
- Envelope rejects string timestamps and naive datetimes.
- `IntakeEstimationRequest` carries image URI and `MealLabel`, not raw model output or a free-text meal label.
- Domain event names remain stable string enum values such as `HumanReviewRequired`.
- Domain event payload can carry integer safety or business codes.
- Domain events reject bare string names and naive datetimes.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_ports -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.ports'`.

- [ ] **Step 3: Implement extension ports and events**

Create `src/medidiet/ports.py`, using the current file as source of truth. Implement:

- `RecommendationRequestEnvelope` with timezone-aware `created_at` and `to_dict()`.
- `IntakeEstimationRequest` with `MealLabel` and `to_dict()`.
- Stable string `EventName` enum.
- `DomainEvent` with timezone-aware `created_at` and `to_dict()`.
- `IntakeEstimatorPort`.
- `MenuProviderPort`.
- `PatientContextPort`.
- `EventPublisherPort`.

- [ ] **Step 4: Run ports and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_ports -v
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/ports.py tests/test_ports.py
git commit -m "feat: add extension ports and events"
```

---

### Task 11: Fixtures and CLI Demo

**Files:**
- Create: `src/medidiet/fixtures.py`
- Create: `src/medidiet/cli.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Add a failing fixture-driven engine test**

Append a test to `tests/test_engine.py` inside `RecommendationEngineTest` that verifies:

- `demo_request()` returns `PatientProfile`, `list[IntakeRecord]`, `list[MenuItem]`, and `MealLabel`.
- The engine accepts the returned `MealLabel` directly, not a free-text string.
- The trace JSON starts with `{` and contains `"traceId"`, `"outcome"`, and the returned outcome value.
- The fixture test imports `medidiet.fixtures`, so it fails before the fixture module exists.

Code: use the current `tests/test_engine.py` as source of truth.

- [ ] **Step 2: Run the updated engine test and verify it fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_engine.RecommendationEngineTest.test_fixture_demo_returns_trace_json -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.fixtures'`.

- [ ] **Step 3: Implement deterministic fixtures and CLI**

Create `src/medidiet/fixtures.py` with:

- A deterministic `DEMO_NOW` timezone-aware timestamp.
- `demo_request() -> tuple[PatientProfile, list[IntakeRecord], list[MenuItem], MealLabel]`.
- Patient conditions, allergens, taste preferences, ingredients, nutrition tags, and contraindication tags represented as `ConceptCode`.
- `IntakeRecord.occurred_at` and `IntakeRecord.meal_label`, with no string `meal_time`.
- One safe, recommendable menu item and one filtered menu item marked `available=False`.

Create `src/medidiet/cli.py` with:

- A `main()` function that loads the baseline rule pack, calls `demo_request()`, runs `RecommendationEngine(..., now=DEMO_NOW)`, and prints only `result.trace.to_json()`.
- No free-text meal label input; it uses the fixture's returned `MealLabel`.

Code: use the current `src/medidiet/fixtures.py` and `src/medidiet/cli.py` as source of truth.

- [ ] **Step 4: Run fixture test, full tests, and CLI**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_engine.RecommendationEngineTest.test_fixture_demo_returns_trace_json -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
```

Expected:
- Test commands PASS.
- CLI prints JSON containing `"traceId"` and `"outcome"`.

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-05-15-recommendation-engine-core.md docs/superpowers/plans/2026-05-15-recommendation-engine-core.zh.md src/medidiet/fixtures.py src/medidiet/cli.py tests/test_engine.py
git commit -m "feat: add demo fixtures and CLI"
```

---

### Task 12: Public Exports and Final Verification

**Files:**
- Modify: `src/medidiet/__init__.py`
- Create: `tests/test_public_api.py`
- Modify: `docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.md` if implementation notes are needed

- [ ] **Step 1: Write failing public API test**

Create `tests/test_public_api.py` verifying:

- `RecommendationEngine`, `RecommendationResult`, `RulePack`, and `load_baseline_rule_pack` can be imported from `medidiet`.
- `medidiet.__all__` exactly lists those four public names.
- `load_baseline_rule_pack()` returns a `RulePack`.
- `RecommendationEngine(rule_pack)` can be constructed from the public API.

Code: use the current `tests/test_public_api.py` as source of truth.

- [ ] **Step 2: Run public API test and verify it fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api -v
```

Expected: FAIL with `ImportError` for the missing public API exports.

- [ ] **Step 3: Export stable public API**

Replace `src/medidiet/__init__.py` with:

```python
"""MediDiet recommendation engine core."""

from medidiet.engine import RecommendationEngine, RecommendationResult
from medidiet.rules import RulePack, load_baseline_rule_pack

__version__ = "0.1.0"

__all__ = [
    "RecommendationEngine",
    "RecommendationResult",
    "RulePack",
    "load_baseline_rule_pack",
]
```

- [ ] **Step 4: Run public API and full verification**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
git status --short
```

Expected:
- Public API test PASS.
- Full suite PASS.
- CLI prints JSON containing `"traceId"` and `"outcome"`.
- `git status --short` shows only intended modified/untracked implementation files before commit.

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-05-15-recommendation-engine-core.md docs/superpowers/plans/2026-05-15-recommendation-engine-core.zh.md src/medidiet/__init__.py tests/test_public_api.py
git commit -m "feat: expose recommendation engine public API"
```

- [ ] **Step 6: Final implementation verification**

Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
git log --oneline -5
```

Expected:
- All tests PASS.
- CLI emits a recommendation trace JSON.
- Recent commits include each task commit from this plan.

---

## Self-Review

### Spec Coverage

- Adult chronic disease and allergy scope: Tasks 2, 3, 4, 9.
- Safety boundary and high-risk escalation: Tasks 4 and 9.
- Clinical reference governance and versioned rule pack: Task 3.
- Rules-first architecture with LLM boundary represented as explanation-only logic: Tasks 8 and 9.
- Data model: Task 2.
- Recommendation flow: Tasks 4 through 9.
- Ranking strategy: Task 7.
- Human review: Tasks 4, 8, 9, 10.
- Error handling and degradation: Tasks 4, 7, 9.
- API and extensibility boundary: Task 10.
- Testing strategy: every task includes failing tests and verification commands.
- Roadmap Phase 1: Tasks 1 through 12.

### Intentional Deferrals

- Real clinical nutrient thresholds require clinician-approved rule-pack work after this core is in place.
- Mini-program UI, production API server, real photo recognition, real delivery connector, HIS/EMR integration, LLM provider integration, and review-console UI need separate implementation plans.

### Placeholder Scan

The plan contains no unresolved placeholder markers or vague deferred implementation steps. Each implementation step has concrete file paths, code, commands, and expected verification output.

### Type Consistency

The same names are used across tasks:

- `PatientProfile`, `IntakeRecord`, `MenuItem`, `Nutrients`, `Confidence`, `Preference`.
- `RulePack`, `ConditionRule`, `load_baseline_rule_pack`.
- `SafetyGate.evaluate`.
- `DailyNutritionCalculator.next_meal_target`.
- `MealPlanGenerator.generate`.
- `MenuMatcher.match`.
- `ExplanationBuilder`.
- `RecommendationTrace`.
- `RecommendationEngine.recommend`.
- `RecommendationRequestEnvelope`, `DomainEvent`, `EventName`.
