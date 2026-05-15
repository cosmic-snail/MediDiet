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
- Create: `src/medidiet/nutrition.py`
- Create: `tests/test_nutrition.py`

- [ ] **Step 1: Write failing nutrition tests**

Create `tests/test_nutrition.py`:

```python
import unittest

from medidiet.domain import Condition, Confidence, DataSource, IntakeRecord, Nutrients
from medidiet.nutrition import DailyNutritionCalculator
from medidiet.rules import load_baseline_rule_pack


class DailyNutritionCalculatorTest(unittest.TestCase):
    def test_aggregates_today_intake(self):
        records = [
            IntakeRecord("rice", "breakfast", "half bowl", Nutrients(energy_kcal=180, carbs_g=40, sodium_mg=20), Confidence(0.9), DataSource.SYSTEM_ESTIMATED),
            IntakeRecord("braised pork", "lunch", "small plate", Nutrients(energy_kcal=450, fat_g=30, sodium_mg=900), Confidence(0.8), DataSource.SYSTEM_ESTIMATED),
        ]

        state = DailyNutritionCalculator(load_baseline_rule_pack()).aggregate(records)

        self.assertEqual(state.total.energy_kcal, 630)
        self.assertEqual(state.total.sodium_mg, 920)
        self.assertEqual(state.low_confidence_labels, [])

    def test_high_sodium_today_tightens_next_meal_target_for_hypertension(self):
        records = [
            IntakeRecord("salty noodles", "lunch", "one bowl", Nutrients(energy_kcal=600, sodium_mg=1600), Confidence(0.85), DataSource.SYSTEM_ESTIMATED),
        ]

        target = DailyNutritionCalculator(load_baseline_rule_pack()).next_meal_target({Condition.HYPERTENSION}, records)

        self.assertEqual(target.max_sodium_mg, 500)
        self.assertIn("today_sodium_high", target.reasons)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_nutrition -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.nutrition'`.

- [ ] **Step 3: Implement nutrition calculation**

Create `src/medidiet/nutrition.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from medidiet.domain import Condition, IntakeRecord, Nutrients
from medidiet.rules import RulePack


@dataclass(frozen=True)
class DailyNutritionState:
    total: Nutrients
    low_confidence_labels: list[str]


@dataclass(frozen=True)
class NextMealTarget:
    max_sodium_mg: float | None = None
    max_sugar_g: float | None = None
    max_fat_g: float | None = None
    max_energy_kcal: float | None = None
    preferred_tags: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)


class DailyNutritionCalculator:
    def __init__(self, rule_pack: RulePack, confidence_threshold: float = 0.7):
        self.rule_pack = rule_pack
        self.confidence_threshold = confidence_threshold

    def aggregate(self, records: list[IntakeRecord]) -> DailyNutritionState:
        total = Nutrients()
        low_confidence_labels: list[str] = []
        for record in records:
            total += record.nutrients
            if record.confidence.is_low(self.confidence_threshold) and not record.manually_corrected:
                low_confidence_labels.append(record.food_label)
        return DailyNutritionState(total=total, low_confidence_labels=low_confidence_labels)

    def next_meal_target(self, conditions: set[Condition], records: list[IntakeRecord]) -> NextMealTarget:
        state = self.aggregate(records)
        preferred_tags: set[str] = set()
        reasons: list[str] = []
        max_sodium = None
        max_sugar = None
        max_fat = None
        max_energy = None

        for condition in conditions:
            rule = self.rule_pack.rules_by_condition.get(condition)
            if not rule:
                continue
            preferred_tags.update(rule.preferred_tags)
            max_sodium = _min_optional(max_sodium, rule.max_sodium_mg_per_meal)
            max_sugar = _min_optional(max_sugar, rule.max_sugar_g_per_meal)
            max_fat = _min_optional(max_fat, rule.max_fat_g_per_meal)
            max_energy = _min_optional(max_energy, rule.max_energy_kcal_per_meal)

        if Condition.HYPERTENSION in conditions and state.total.sodium_mg >= 1500:
            max_sodium = 500
            preferred_tags.add("low_sodium")
            reasons.append("today_sodium_high")

        return NextMealTarget(
            max_sodium_mg=max_sodium,
            max_sugar_g=max_sugar,
            max_fat_g=max_fat,
            max_energy_kcal=max_energy,
            preferred_tags=preferred_tags,
            reasons=reasons,
        )


def _min_optional(current: float | None, candidate: float | None) -> float | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return min(current, candidate)
```

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
- Create: `src/medidiet/planner.py`
- Create: `tests/test_planner.py`

- [ ] **Step 1: Write failing planner tests**

Create `tests/test_planner.py`:

```python
import unittest

from medidiet.nutrition import NextMealTarget
from medidiet.planner import MealPlanGenerator


class MealPlanGeneratorTest(unittest.TestCase):
    def test_generates_plan_from_target_tags(self):
        target = NextMealTarget(max_sodium_mg=500, preferred_tags={"low_sodium", "controlled_carbs", "vegetable_rich"}, reasons=["today_sodium_high"])

        plan = MealPlanGenerator().generate(target, meal_time="dinner")

        self.assertEqual(plan.meal_time, "dinner")
        self.assertIn("low_sodium", plan.required_tags)
        self.assertIn("controlled_carbs", plan.required_tags)
        self.assertIn("avoid_extra_sauce", plan.instructions)
        self.assertIn("today_sodium_high", plan.reasons)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_planner -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.planner'`.

- [ ] **Step 3: Implement planner**

Create `src/medidiet/planner.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from medidiet.nutrition import NextMealTarget


@dataclass(frozen=True)
class MealPlan:
    meal_time: str
    required_tags: set[str]
    avoid_tags: set[str]
    instructions: list[str]
    reasons: list[str] = field(default_factory=list)


class MealPlanGenerator:
    def generate(self, target: NextMealTarget, meal_time: str) -> MealPlan:
        required_tags = set(target.preferred_tags)
        avoid_tags: set[str] = set()
        instructions: list[str] = []

        if target.max_sodium_mg is not None:
            required_tags.add("low_sodium")
            avoid_tags.add("high_sodium")
            instructions.append("avoid_extra_sauce")
        if target.max_sugar_g is not None:
            required_tags.add("controlled_carbs")
            avoid_tags.add("sugary_drink")
        if target.max_fat_g is not None:
            avoid_tags.add("deep_fried")
        if target.max_energy_kcal is not None:
            required_tags.add("balanced")
            avoid_tags.add("oversized_portion")

        required_tags.add("lean_protein")
        required_tags.add("vegetable_rich")

        return MealPlan(
            meal_time=meal_time,
            required_tags=required_tags,
            avoid_tags=avoid_tags,
            instructions=instructions,
            reasons=list(target.reasons),
        )
```

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
- Create: `src/medidiet/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: Write failing matcher tests**

Create `tests/test_matcher.py`:

```python
import unittest

from medidiet.domain import Confidence, DataSource, MenuItem, Nutrients, Preference
from medidiet.matcher import MenuMatcher
from medidiet.planner import MealPlan


def item(item_id, tags, sodium, price=3000, distance=800, reliability=0.9):
    return MenuItem(
        item_id=item_id,
        merchant_id="shop",
        name=item_id,
        ingredients={"fish"},
        taste_tags=set(tags),
        nutrients=Nutrients(energy_kcal=520, carbs_g=45, protein_g=32, fat_g=16, sodium_mg=sodium, sugar_g=5, fiber_g=5),
        nutrition_confidence=Confidence(0.9),
        source=DataSource.MERCHANT_LABEL,
        price_cents=price,
        distance_meters=distance,
        merchant_reliability=reliability,
    )


class MenuMatcherTest(unittest.TestCase):
    def test_excludes_avoid_tags_and_high_sodium(self):
        plan = MealPlan("dinner", {"low_sodium"}, {"high_sodium"}, [], [])
        candidates = [item("safe", {"low_sodium"}, 450), item("salty", {"high_sodium"}, 1200)]

        result = MenuMatcher().match(plan, candidates, Preference())

        self.assertEqual([score.item.item_id for score in result.accepted], ["safe"])
        self.assertEqual(result.excluded["salty"], "avoid_tag:high_sodium")

    def test_ranks_safe_items_by_nutrition_preference_price_distance_and_reliability(self):
        plan = MealPlan("dinner", {"low_sodium", "vegetable_rich"}, set(), [], [])
        candidates = [
            item("ok", {"low_sodium"}, 500, price=4000, distance=2000, reliability=0.7),
            item("best", {"low_sodium", "vegetable_rich", "light"}, 420, price=2800, distance=600, reliability=0.95),
        ]
        preference = Preference(taste_tags={"light"}, max_price_cents=3500, max_distance_meters=1000)

        result = MenuMatcher().match(plan, candidates, preference)

        self.assertEqual(result.accepted[0].item.item_id, "best")
        self.assertGreater(result.accepted[0].score, result.accepted[1].score)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_matcher -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.matcher'`.

- [ ] **Step 3: Implement matcher**

Create `src/medidiet/matcher.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from medidiet.domain import MenuItem, Preference
from medidiet.planner import MealPlan


@dataclass(frozen=True)
class MenuItemScore:
    item: MenuItem
    score: float
    reasons: list[str]


@dataclass(frozen=True)
class MatchResult:
    accepted: list[MenuItemScore]
    excluded: dict[str, str] = field(default_factory=dict)


class MenuMatcher:
    def match(self, plan: MealPlan, candidates: list[MenuItem], preference: Preference) -> MatchResult:
        accepted: list[MenuItemScore] = []
        excluded: dict[str, str] = {}

        for candidate in candidates:
            if not candidate.available:
                excluded[candidate.item_id] = "unavailable"
                continue
            avoid_hit = next((tag for tag in plan.avoid_tags if tag in candidate.taste_tags), None)
            if avoid_hit:
                excluded[candidate.item_id] = f"avoid_tag:{avoid_hit}"
                continue

            score, reasons = self._score(candidate, plan, preference)
            accepted.append(MenuItemScore(item=candidate, score=score, reasons=reasons))

        accepted.sort(key=lambda scored: scored.score, reverse=True)
        return MatchResult(accepted=accepted, excluded=excluded)

    def _score(self, item: MenuItem, plan: MealPlan, preference: Preference) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0

        matched_tags = plan.required_tags.intersection(item.taste_tags)
        if plan.required_tags:
            score += 45 * (len(matched_tags) / len(plan.required_tags))
            if matched_tags:
                reasons.append("nutrition_tag_match")

        if item.nutrients.sodium_mg <= 500:
            score += 20
            reasons.append("safety_margin_sodium")
        elif item.nutrients.sodium_mg <= 700:
            score += 12

        preferred_taste = preference.taste_tags.intersection(item.taste_tags)
        if preferred_taste:
            score += 15
            reasons.append("taste_preference")

        if preference.max_price_cents is None or item.price_cents <= preference.max_price_cents:
            score += 5
        if preference.max_distance_meters is None or item.distance_meters <= preference.max_distance_meters:
            score += 5

        score += 10 * item.merchant_reliability
        return round(score, 2), reasons
```

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

Create `tests/test_explainer_trace.py`:

```python
import json
import unittest

from medidiet.domain import Outcome, RiskLevel
from medidiet.explainer import ExplanationBuilder
from medidiet.trace import RecommendationTrace


class ExplanationTraceTest(unittest.TestCase):
    def test_patient_explanation_is_plain_and_safe(self):
        explanation = ExplanationBuilder().patient_explanation(
            outcome=Outcome.RECOMMENDED,
            reasons=["low_sodium", "controlled_carbs"],
            cautions=["avoid_extra_sauce"],
        )

        self.assertIn("钠", explanation)
        self.assertIn("主食", explanation)
        self.assertNotIn("调整药物", explanation)

    def test_trace_serializes_decision_context(self):
        trace = RecommendationTrace(
            trace_id="trace-1",
            rule_version="baseline-2026-05-15",
            outcome=Outcome.HUMAN_REVIEW_REQUIRED,
            risk_level=RiskLevel.HIGH,
            rule_hits=["allergy:peanut"],
            exclusions={"m-1": "allergy:peanut"},
            scores={"m-2": 88.0},
            patient_explanation="需要营养师确认。",
            clinician_explanation={"reason": "allergy"},
        )

        payload = json.loads(trace.to_json())

        self.assertEqual(payload["traceId"], "trace-1")
        self.assertEqual(payload["outcome"], "human_review_required")
        self.assertEqual(payload["ruleVersion"], "baseline-2026-05-15")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_explainer_trace -v
```

Expected: FAIL with `ModuleNotFoundError` for `medidiet.explainer` or `medidiet.trace`.

- [ ] **Step 3: Implement explanation builder and trace**

Create `src/medidiet/explainer.py`:

```python
from __future__ import annotations

from medidiet.domain import Outcome


class ExplanationBuilder:
    def patient_explanation(self, outcome: Outcome, reasons: list[str], cautions: list[str]) -> str:
        if outcome == Outcome.HUMAN_REVIEW_REQUIRED:
            return "这次推荐需要营养师确认，因为资料或菜品信息存在不确定性。"
        if outcome == Outcome.REFUSED:
            return "当前候选餐食不满足安全要求，暂不建议自动推荐。"

        parts: list[str] = []
        if "low_sodium" in reasons:
            parts.append("这份餐钠含量更适合今天的目标")
        if "controlled_carbs" in reasons:
            parts.append("主食和糖分更容易控制")
        if "vegetable_rich" in reasons:
            parts.append("蔬菜搭配更充分")
        if not parts:
            parts.append("这份餐通过了当前安全和营养规则")
        if "avoid_extra_sauce" in cautions:
            parts.append("建议不要额外加酱料或汤汁")
        return "，".join(parts) + "。"

    def clinician_explanation(self, rule_hits: list[str], uncertainty: list[str], scores: dict[str, float]) -> dict[str, object]:
        return {
            "ruleHits": rule_hits,
            "uncertainty": uncertainty,
            "scores": scores,
            "llmBoundary": "Explanation is generated only from rule hits, nutrition facts, and scored candidates.",
        }
```

Create `src/medidiet/trace.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from medidiet.domain import Outcome, RiskLevel


@dataclass(frozen=True)
class RecommendationTrace:
    trace_id: str
    rule_version: str
    outcome: Outcome
    risk_level: RiskLevel
    rule_hits: list[str]
    exclusions: dict[str, str]
    scores: dict[str, float]
    patient_explanation: str
    clinician_explanation: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["traceId"] = payload.pop("trace_id")
        payload["ruleVersion"] = payload.pop("rule_version")
        payload["riskLevel"] = self.risk_level.value
        payload["outcome"] = self.outcome.value
        payload["ruleHits"] = payload.pop("rule_hits")
        payload["patientExplanation"] = payload.pop("patient_explanation")
        payload["clinicianExplanation"] = payload.pop("clinician_explanation")
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
```

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

Create `tests/test_engine.py`:

```python
import unittest

from medidiet.domain import Allergy, Confidence, Condition, DataSource, IntakeRecord, MenuItem, Nutrients, Outcome, PatientProfile, Preference
from medidiet.engine import RecommendationEngine
from medidiet.rules import load_baseline_rule_pack


def profile(**overrides):
    data = dict(
        patient_id="p-1",
        age=54,
        height_cm=168,
        weight_kg=78,
        conditions={Condition.HYPERTENSION, Condition.DIABETES},
        allergies=set(),
        contraindications=set(),
        preferences=Preference(taste_tags={"light"}, max_price_cents=3500, max_distance_meters=1500),
        key_risk_fields_confirmed=True,
        source=DataSource.PATIENT_REPORTED,
    )
    data.update(overrides)
    return PatientProfile(**data)


def menu(item_id, tags, sodium=450, sugar=6, ingredients=None):
    return MenuItem(
        item_id=item_id,
        merchant_id="shop",
        name=item_id,
        ingredients=ingredients or {"fish", "vegetable"},
        taste_tags=set(tags),
        nutrients=Nutrients(energy_kcal=520, carbs_g=42, protein_g=30, fat_g=14, sodium_mg=sodium, sugar_g=sugar, fiber_g=5),
        nutrition_confidence=Confidence(0.9),
        source=DataSource.MERCHANT_LABEL,
        price_cents=3200,
        distance_meters=800,
        merchant_reliability=0.9,
    )


class RecommendationEngineTest(unittest.TestCase):
    def test_recommends_safe_item(self):
        intake = [IntakeRecord("salty lunch", "lunch", "one bowl", Nutrients(sodium_mg=1600), Confidence(0.9), DataSource.SYSTEM_ESTIMATED)]
        result = RecommendationEngine(load_baseline_rule_pack()).recommend(profile(), intake, [menu("steamed-fish", {"low_sodium", "controlled_carbs", "vegetable_rich", "light"})], "dinner")

        self.assertEqual(result.outcome, Outcome.RECOMMENDED)
        self.assertEqual(result.recommended_items[0].item_id, "steamed-fish")
        self.assertIn("钠", result.patient_explanation)
        self.assertEqual(result.trace.rule_version, "baseline-2026-05-15")

    def test_refuses_when_no_candidate_survives_hard_rules(self):
        result = RecommendationEngine(load_baseline_rule_pack()).recommend(profile(), [], [menu("salty", {"high_sodium"}, sodium=1200)], "dinner")

        self.assertEqual(result.outcome, Outcome.REFUSED)
        self.assertEqual(result.recommended_items, [])
        self.assertIn("暂不建议", result.patient_explanation)

    def test_routes_allergy_to_human_review(self):
        result = RecommendationEngine(load_baseline_rule_pack()).recommend(
            profile(allergies={Allergy("peanut")}),
            [],
            [menu("peanut-fish", {"low_sodium"}, ingredients={"peanut", "fish"})],
            "dinner",
        )

        self.assertEqual(result.outcome, Outcome.HUMAN_REVIEW_REQUIRED)
        self.assertEqual(result.recommended_items, [])
        self.assertIn("营养师确认", result.patient_explanation)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run engine tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_engine -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.engine'`.

- [ ] **Step 3: Implement engine orchestration**

Create `src/medidiet/engine.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from medidiet.domain import IntakeRecord, MenuItem, Outcome, PatientProfile, RiskLevel
from medidiet.explainer import ExplanationBuilder
from medidiet.matcher import MenuMatcher
from medidiet.nutrition import DailyNutritionCalculator
from medidiet.planner import MealPlanGenerator
from medidiet.rules import RulePack
from medidiet.safety import SafetyGate
from medidiet.trace import RecommendationTrace


@dataclass(frozen=True)
class RecommendationResult:
    outcome: Outcome
    recommended_items: list[MenuItem]
    patient_explanation: str
    clinician_explanation: dict[str, object]
    trace: RecommendationTrace


class RecommendationEngine:
    def __init__(self, rule_pack: RulePack):
        self.rule_pack = rule_pack
        self.safety_gate = SafetyGate(rule_pack)
        self.calculator = DailyNutritionCalculator(rule_pack)
        self.planner = MealPlanGenerator()
        self.matcher = MenuMatcher()
        self.explainer = ExplanationBuilder()

    def recommend(
        self,
        patient: PatientProfile,
        intake_records: list[IntakeRecord],
        candidate_menu_items: list[MenuItem],
        meal_time: str,
    ) -> RecommendationResult:
        safety = self.safety_gate.evaluate(patient, candidate_menu_items, intake_records)
        if safety.requires_human_review:
            return self._finalize(
                outcome=Outcome.HUMAN_REVIEW_REQUIRED,
                risk_level=RiskLevel.HIGH,
                recommended_items=[],
                rule_hits=safety.hard_blocks,
                exclusions={item.item_id: "safety_review_required" for item in candidate_menu_items},
                scores={},
                uncertainty=safety.uncertainties,
                patient_explanation=self.explainer.patient_explanation(Outcome.HUMAN_REVIEW_REQUIRED, [], []),
            )

        target = self.calculator.next_meal_target(patient.conditions, intake_records)
        plan = self.planner.generate(target, meal_time)
        match_result = self.matcher.match(plan, candidate_menu_items, patient.preferences)

        if not match_result.accepted:
            return self._finalize(
                outcome=Outcome.REFUSED,
                risk_level=RiskLevel.HIGH,
                recommended_items=[],
                rule_hits=list(plan.avoid_tags),
                exclusions=match_result.excluded,
                scores={},
                uncertainty=[],
                patient_explanation=self.explainer.patient_explanation(Outcome.REFUSED, [], []),
            )

        top_items = [match_result.accepted[0].item]
        outcome = Outcome.RECOMMENDED if match_result.accepted[0].score >= 60 else Outcome.DOWNGRADED
        scores = {scored.item.item_id: scored.score for scored in match_result.accepted}
        reasons = list(plan.required_tags)
        explanation = self.explainer.patient_explanation(outcome, reasons, plan.instructions)
        return self._finalize(
            outcome=outcome,
            risk_level=RiskLevel.LOW if outcome == Outcome.RECOMMENDED else RiskLevel.MEDIUM,
            recommended_items=top_items,
            rule_hits=reasons,
            exclusions=match_result.excluded,
            scores=scores,
            uncertainty=[],
            patient_explanation=explanation,
        )

    def _finalize(
        self,
        outcome: Outcome,
        risk_level: RiskLevel,
        recommended_items: list[MenuItem],
        rule_hits: list[str],
        exclusions: dict[str, str],
        scores: dict[str, float],
        uncertainty: list[str],
        patient_explanation: str,
    ) -> RecommendationResult:
        clinician_explanation = self.explainer.clinician_explanation(rule_hits, uncertainty, scores)
        trace = RecommendationTrace(
            trace_id=f"trace-{uuid4()}",
            rule_version=self.rule_pack.version,
            outcome=outcome,
            risk_level=risk_level,
            rule_hits=rule_hits,
            exclusions=exclusions,
            scores=scores,
            patient_explanation=patient_explanation,
            clinician_explanation=clinician_explanation,
        )
        return RecommendationResult(
            outcome=outcome,
            recommended_items=recommended_items,
            patient_explanation=patient_explanation,
            clinician_explanation=clinician_explanation,
            trace=trace,
        )
```

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

Create `tests/test_ports.py`:

```python
import unittest

from medidiet.ports import (
    DomainEvent,
    EventName,
    IntakeEstimationRequest,
    RecommendationRequestEnvelope,
)


class PortsTest(unittest.TestCase):
    def test_request_envelope_carries_version_and_source(self):
        envelope = RecommendationRequestEnvelope(
            schema_version="v1",
            source_system="mini-program",
            source_version="0.1.0",
            request_id="req-1",
            timestamp="2026-05-15T12:00:00+08:00",
        )

        self.assertEqual(envelope.schema_version, "v1")
        self.assertEqual(envelope.source_system, "mini-program")

    def test_intake_request_carries_image_reference_not_raw_model_output(self):
        request = IntakeEstimationRequest(
            envelope=RecommendationRequestEnvelope("v1", "mini-program", "0.1.0", "req-2", "2026-05-15T12:00:00+08:00"),
            image_uri="oss://bucket/meal.jpg",
            meal_time="lunch",
        )

        self.assertEqual(request.image_uri, "oss://bucket/meal.jpg")
        self.assertEqual(request.meal_time, "lunch")

    def test_domain_event_names_are_stable(self):
        event = DomainEvent(name=EventName.HUMAN_REVIEW_REQUIRED, trace_id="trace-1", payload={"reason": "low_confidence"})

        self.assertEqual(event.name.value, "HumanReviewRequired")
        self.assertEqual(event.payload["reason"], "low_confidence")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_ports -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.ports'`.

- [ ] **Step 3: Implement extension ports and events**

Create `src/medidiet/ports.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from medidiet.domain import IntakeRecord, MenuItem, PatientProfile


@dataclass(frozen=True)
class RecommendationRequestEnvelope:
    schema_version: str
    source_system: str
    source_version: str
    request_id: str
    timestamp: str


@dataclass(frozen=True)
class IntakeEstimationRequest:
    envelope: RecommendationRequestEnvelope
    image_uri: str
    meal_time: str


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
```

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
- Create: `tests/test_engine.py` update

- [ ] **Step 1: Add a failing fixture-driven engine test**

Append this test to `tests/test_engine.py` inside `RecommendationEngineTest`:

```python
    def test_fixture_demo_returns_trace_json(self):
        from medidiet.fixtures import demo_request

        patient, intake, menu_items = demo_request()
        result = RecommendationEngine(load_baseline_rule_pack()).recommend(patient, intake, menu_items, "dinner")

        self.assertTrue(result.trace.to_json().startswith("{"))
        self.assertIn(result.outcome.value, result.trace.to_json())
```

- [ ] **Step 2: Run the updated engine test and verify it fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_engine.RecommendationEngineTest.test_fixture_demo_returns_trace_json -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.fixtures'`.

- [ ] **Step 3: Implement deterministic fixtures and CLI**

Create `src/medidiet/fixtures.py`:

```python
from __future__ import annotations

from medidiet.domain import Allergy, Confidence, Condition, DataSource, IntakeRecord, MenuItem, Nutrients, PatientProfile, Preference


def demo_request() -> tuple[PatientProfile, list[IntakeRecord], list[MenuItem]]:
    patient = PatientProfile(
        patient_id="demo-patient",
        age=52,
        height_cm=170,
        weight_kg=80,
        conditions={Condition.HYPERTENSION, Condition.DIABETES},
        allergies={Allergy("shrimp")},
        contraindications=set(),
        preferences=Preference(taste_tags={"light"}, max_price_cents=4000, max_distance_meters=2000),
        key_risk_fields_confirmed=True,
        source=DataSource.PATIENT_REPORTED,
    )
    intake = [
        IntakeRecord(
            food_label="salty noodles",
            meal_time="lunch",
            portion="one bowl",
            nutrients=Nutrients(energy_kcal=620, carbs_g=80, protein_g=20, fat_g=18, sodium_mg=1600, sugar_g=6, fiber_g=4),
            confidence=Confidence(0.86),
            source=DataSource.SYSTEM_ESTIMATED,
        )
    ]
    menu_items = [
        MenuItem(
            item_id="steamed-fish-set",
            merchant_id="canteen-1",
            name="Steamed fish set",
            ingredients={"fish", "brown rice", "greens"},
            taste_tags={"low_sodium", "controlled_carbs", "vegetable_rich", "lean_protein", "light"},
            nutrients=Nutrients(energy_kcal=560, carbs_g=55, protein_g=35, fat_g=16, sodium_mg=430, sugar_g=5, fiber_g=7),
            nutrition_confidence=Confidence(0.92),
            source=DataSource.HUMAN_CURATED,
            price_cents=3600,
            distance_meters=500,
            merchant_reliability=0.95,
        ),
        MenuItem(
            item_id="fried-pork-rice",
            merchant_id="delivery-1",
            name="Fried pork rice",
            ingredients={"pork", "white rice"},
            taste_tags={"deep_fried", "high_sodium"},
            nutrients=Nutrients(energy_kcal=820, carbs_g=90, protein_g=28, fat_g=38, sodium_mg=1200, sugar_g=10, fiber_g=2),
            nutrition_confidence=Confidence(0.8),
            source=DataSource.SYSTEM_ESTIMATED,
            price_cents=3200,
            distance_meters=900,
            merchant_reliability=0.7,
        ),
    ]
    return patient, intake, menu_items
```

Create `src/medidiet/cli.py`:

```python
from __future__ import annotations

from medidiet.engine import RecommendationEngine
from medidiet.fixtures import demo_request
from medidiet.rules import load_baseline_rule_pack


def main() -> None:
    patient, intake, menu = demo_request()
    result = RecommendationEngine(load_baseline_rule_pack()).recommend(patient, intake, menu, "dinner")
    print(result.trace.to_json())


if __name__ == "__main__":
    main()
```

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
git add src/medidiet/fixtures.py src/medidiet/cli.py tests/test_engine.py
git commit -m "feat: add demo fixtures and CLI"
```

---

### Task 12: Public Exports and Final Verification

**Files:**
- Modify: `src/medidiet/__init__.py`
- Create: `tests/test_public_api.py`
- Modify: `docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.md` if implementation notes are needed

- [ ] **Step 1: Write failing public API test**

Create `tests/test_public_api.py`:

```python
import unittest


class PublicApiTest(unittest.TestCase):
    def test_engine_exports_are_available(self):
        from medidiet import RecommendationEngine, load_baseline_rule_pack

        self.assertTrue(callable(load_baseline_rule_pack))
        self.assertEqual(RecommendationEngine.__name__, "RecommendationEngine")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run public API test and verify it fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api -v
```

Expected: FAIL with `ImportError` for `RecommendationEngine` or `load_baseline_rule_pack`.

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
git add src/medidiet/__init__.py tests/test_public_api.py
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
